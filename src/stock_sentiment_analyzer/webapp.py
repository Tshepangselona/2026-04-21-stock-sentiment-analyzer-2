from __future__ import annotations

import json
from pathlib import Path
from wsgiref.simple_server import make_server

from stock_sentiment_analyzer.analyzer import HeadlineInput, SentimentAnalyzer
from stock_sentiment_analyzer.data_sources import FetchRequest, NewsSourceError, get_provider


STATIC_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app():
    analyzer = SentimentAnalyzer()

    def app(environ, start_response):
        method = environ["REQUEST_METHOD"]
        path = environ.get("PATH_INFO", "/")

        if method == "GET" and path == "/":
            return _serve_file(start_response, STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if method == "GET" and path == "/app.css":
            return _serve_file(start_response, STATIC_DIR / "app.css", "text/css; charset=utf-8")
        if method == "GET" and path == "/app.js":
            return _serve_file(start_response, STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if method == "POST" and path == "/api/analyze":
            body = _read_json_body(environ)
            try:
                inputs = _normalize_manual_inputs(body)
                result = analyzer.analyze(inputs)
            except ValueError as exc:
                return _json(start_response, 400, {"error": str(exc)})
            return _json(
                start_response,
                200,
                {
                    **result.to_dict(),
                    "meta": {
                        "mode": "manual",
                        "headline_count_before_filter": len(inputs),
                        "headline_count_after_filter": result.headline_count,
                    },
                },
            )
        if method == "POST" and path == "/api/fetch":
            body = _read_json_body(environ)
            try:
                provider_name = str(body.get("provider", ""))
                provider = get_provider(str(body.get("provider", "")))
                request = FetchRequest(
                    ticker=_none_if_blank(body.get("ticker")),
                    query=_none_if_blank(body.get("query")),
                    limit=int(body.get("limit", 8)),
                )
                headlines = provider.fetch(
                    request
                )
                result = analyzer.analyze(headlines)
            except (NewsSourceError, ValueError) as exc:
                return _json(start_response, 400, {"error": str(exc)})
            return _json(
                start_response,
                200,
                {
                    **result.to_dict(),
                    "meta": {
                        "mode": "live",
                        "provider": provider_name,
                        "ticker": request.ticker,
                        "query": request.query,
                        "headline_count_before_filter": int(body.get("limit", 8)),
                        "headline_count_after_filter": result.headline_count,
                    },
                },
            )

        return _json(start_response, 404, {"error": "Not found"})

    return app


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    with make_server(host, port, create_app()) as server:
        print(f"Frontend running at http://{host}:{port}")
        server.serve_forever()


def _serve_file(start_response, path: Path, content_type: str):
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return _json(start_response, 404, {"error": "Static asset not found"})
    start_response("200 OK", [("Content-Type", content_type)])
    return [content]


def _read_json_body(environ) -> dict:
    content_length = int(environ.get("CONTENT_LENGTH") or 0)
    raw = environ["wsgi.input"].read(content_length) if content_length else b"{}"
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _normalize_manual_inputs(body: dict) -> list[HeadlineInput]:
    items = body.get("headlines")
    if not isinstance(items, list) or not items:
        raise ValueError("Provide a non-empty 'headlines' list.")
    normalized: list[HeadlineInput] = []
    for item in items:
        if isinstance(item, str) and item.strip():
            normalized.append(HeadlineInput(headline=item.strip()))
            continue
        if isinstance(item, dict):
            headline = item.get("headline")
            if isinstance(headline, str) and headline.strip():
                normalized.append(
                    HeadlineInput(
                        headline=headline.strip(),
                        ticker=_none_if_blank(item.get("ticker")),
                        source=_none_if_blank(item.get("source")),
                    )
                )
    if not normalized:
        raise ValueError("No valid headlines were provided.")
    return normalized


def _none_if_blank(value) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _json(start_response, status: int, payload: dict):
    phrases = {200: "OK", 400: "Bad Request", 404: "Not Found"}
    body = json.dumps(payload).encode("utf-8")
    start_response(
        f"{status} {phrases.get(status, 'OK')}",
        [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))],
    )
    return [body]


if __name__ == "__main__":
    run_server()
