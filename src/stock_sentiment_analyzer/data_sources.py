from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from stock_sentiment_analyzer.analyzer import HeadlineInput


_ENV_LOADED = False


class NewsSourceError(RuntimeError):
    pass


@dataclass(slots=True)
class FetchRequest:
    ticker: str | None = None
    query: str | None = None
    limit: int = 10


class BaseNewsProvider:
    provider_name = "base"

    def fetch(self, request: FetchRequest) -> list[HeadlineInput]:
        raise NotImplementedError

    def _get_required_api_key(self, env_var: str) -> str:
        load_local_env()
        value = os.getenv(env_var)
        if value:
            return value
        raise NewsSourceError(
            f"Missing API key. Set the {env_var} environment variable before using the {self.provider_name} provider."
        )

    def _request_json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{base_url}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=20) as response:
                payload = response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - network path
            raise NewsSourceError(f"Request to {self.provider_name} failed: {exc}") from exc

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise NewsSourceError(f"{self.provider_name} returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise NewsSourceError(f"{self.provider_name} returned an unexpected response shape.")
        return data


class AlphaVantageNewsProvider(BaseNewsProvider):
    provider_name = "alpha_vantage"
    api_key_env_var = "ALPHA_VANTAGE_API_KEY"
    base_url = "https://www.alphavantage.co/query"

    def fetch(self, request: FetchRequest) -> list[HeadlineInput]:
        params: dict[str, Any] = {
            "function": "NEWS_SENTIMENT",
            "apikey": self._get_required_api_key(self.api_key_env_var),
            "limit": max(1, min(request.limit, 50)),
            "sort": "LATEST",
        }
        if request.ticker:
            params["tickers"] = request.ticker.upper()
        if request.query and not request.ticker:
            params["topics"] = request.query

        data = self._request_json(self.base_url, params)
        if "Error Message" in data:
            raise NewsSourceError(str(data["Error Message"]))
        feed = data.get("feed")
        if not isinstance(feed, list):
            raise NewsSourceError("Alpha Vantage response did not include a 'feed' array.")

        headlines: list[HeadlineInput] = []
        ranked_articles = self._rank_articles(feed, request)
        for article in ranked_articles[: request.limit]:
            if not isinstance(article, dict):
                continue
            title = article.get("title")
            if not isinstance(title, str) or not title.strip():
                continue

            source = article.get("source")
            ticker = request.ticker or self._extract_primary_ticker(article)
            headlines.append(
                HeadlineInput(
                    headline=title.strip(),
                    ticker=ticker,
                    source=source if isinstance(source, str) and source.strip() else "Alpha Vantage",
                )
            )
        return headlines

    def _rank_articles(self, feed: list[Any], request: FetchRequest) -> list[dict[str, Any]]:
        ranked: list[tuple[float, dict[str, Any]]] = []
        for article in feed:
            if not isinstance(article, dict):
                continue
            score = self._relevance_score(article, request)
            if score <= 0:
                continue
            ranked.append((score, article))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [article for _, article in ranked]

    def _relevance_score(self, article: dict[str, Any], request: FetchRequest) -> float:
        score = 0.0
        title = article.get("title")
        if not isinstance(title, str):
            return score
        lowered_title = title.casefold()

        if request.ticker:
            ticker = request.ticker.upper()
            for entry in article.get("ticker_sentiment", []):
                if not isinstance(entry, dict):
                    continue
                if str(entry.get("ticker", "")).upper() == ticker:
                    score += 4.0
                    relevance = entry.get("relevance_score")
                    try:
                        score += float(relevance)
                    except (TypeError, ValueError):
                        pass
                    break

            if re.search(rf"\b{re.escape(ticker.casefold())}\b", lowered_title):
                score += 2.5

        if request.query:
            query_terms = [term for term in re.findall(r"[a-z0-9]+", request.query.casefold()) if len(term) > 2]
            score += sum(1.1 for term in query_terms if term in lowered_title)

        return score

    def _extract_primary_ticker(self, article: dict[str, Any]) -> str | None:
        sentiment = article.get("ticker_sentiment")
        if not isinstance(sentiment, list) or not sentiment:
            return None
        first = sentiment[0]
        if not isinstance(first, dict):
            return None
        ticker = first.get("ticker")
        return ticker if isinstance(ticker, str) and ticker.strip() else None


class NewsApiProvider(BaseNewsProvider):
    provider_name = "newsapi"
    api_key_env_var = "NEWSAPI_API_KEY"
    base_url = "https://newsapi.org/v2/everything"

    def fetch(self, request: FetchRequest) -> list[HeadlineInput]:
        search_query = request.query or request.ticker
        if not search_query:
            raise NewsSourceError("NewsAPI requires a ticker or query.")

        params: dict[str, Any] = {
            "apiKey": self._get_required_api_key(self.api_key_env_var),
            "q": search_query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max(1, min(request.limit, 100)),
        }
        data = self._request_json(self.base_url, params)
        status = data.get("status")
        if status != "ok":
            message = data.get("message") or "NewsAPI returned an error."
            raise NewsSourceError(str(message))

        articles = data.get("articles")
        if not isinstance(articles, list):
            raise NewsSourceError("NewsAPI response did not include an 'articles' array.")

        headlines: list[HeadlineInput] = []
        ranked_articles = self._rank_articles(articles, request)
        for article in ranked_articles[: request.limit]:
            if not isinstance(article, dict):
                continue
            title = article.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            source_name = article.get("source", {})
            source = source_name.get("name") if isinstance(source_name, dict) else None
            headlines.append(
                HeadlineInput(
                    headline=title.strip(),
                    ticker=request.ticker.upper() if request.ticker else None,
                    source=source if isinstance(source, str) and source.strip() else "NewsAPI",
                )
            )
        return headlines

    def _rank_articles(self, articles: list[Any], request: FetchRequest) -> list[dict[str, Any]]:
        ranked: list[tuple[float, dict[str, Any]]] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            score = self._relevance_score(article, request)
            if score <= 0:
                continue
            ranked.append((score, article))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [article for _, article in ranked]

    def _relevance_score(self, article: dict[str, Any], request: FetchRequest) -> float:
        title = article.get("title")
        if not isinstance(title, str):
            return 0.0

        lowered_title = title.casefold()
        score = 0.0
        if request.ticker and request.ticker.casefold() in lowered_title:
            score += 2.2

        search_text = " ".join(filter(None, [request.query, request.ticker]))
        search_terms = [term for term in re.findall(r"[a-z0-9]+", search_text.casefold()) if len(term) > 2]
        score += sum(1.0 for term in search_terms if term in lowered_title)
        return score if search_terms else 1.0


def get_provider(name: str) -> BaseNewsProvider:
    normalized = name.strip().lower()
    providers: dict[str, BaseNewsProvider] = {
        "alpha_vantage": AlphaVantageNewsProvider(),
        "alphavantage": AlphaVantageNewsProvider(),
        "newsapi": NewsApiProvider(),
    }
    try:
        return providers[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted({"alpha_vantage", "newsapi"}))
        raise NewsSourceError(f"Unsupported provider '{name}'. Choose one of: {supported}.") from exc


def load_local_env(env_path: Path | None = None) -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    path = env_path or Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        _ENV_LOADED = True
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value

    _ENV_LOADED = True
