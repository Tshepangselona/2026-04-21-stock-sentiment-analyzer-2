from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from stock_sentiment_analyzer.analyzer import HeadlineInput


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
        for article in feed[: request.limit]:
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
        for article in articles[: request.limit]:
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
