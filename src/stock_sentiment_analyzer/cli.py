from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from stock_sentiment_analyzer.analyzer import HeadlineInput, SentimentAnalyzer
from stock_sentiment_analyzer.data_sources import FetchRequest, get_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze stock-related headline sentiment.")
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to a JSON file containing either a list of headlines or {'headlines': [...]}",
    )
    parser.add_argument(
        "--headline",
        action="append",
        default=[],
        help="A single headline to analyze. Repeat the flag for multiple headlines.",
    )
    parser.add_argument(
        "--ticker",
        action="append",
        default=[],
        help="Ticker for the preceding --headline. Repeat to align with multiple --headline values.",
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Source label for the preceding --headline. Repeat to align with multiple --headline values.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--provider",
        choices=("alpha_vantage", "newsapi"),
        help="Fetch live headlines from the selected provider instead of using only local input.",
    )
    parser.add_argument(
        "--query",
        help="Keyword or topic query for live provider fetches.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of live headlines to fetch.",
    )
    return parser


def load_headlines(
    file_path: Path | None,
    cli_headlines: list[str],
    cli_tickers: list[str],
    cli_sources: list[str],
) -> list[str | HeadlineInput | dict[str, str]]:
    headlines: list[str | HeadlineInput | dict[str, str]] = []
    headlines.extend(build_cli_inputs(cli_headlines, cli_tickers, cli_sources))
    if file_path is None:
        return headlines

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        headlines.extend(payload)
    elif isinstance(payload, dict) and isinstance(payload.get("headlines"), list):
        headlines.extend(payload["headlines"])
    else:
        raise ValueError("JSON must be a list of headlines or an object with a 'headlines' list.")
    return headlines


def build_cli_inputs(
    cli_headlines: list[str],
    cli_tickers: list[str],
    cli_sources: list[str],
) -> list[HeadlineInput]:
    if not cli_headlines:
        return []
    if len(cli_tickers) > len(cli_headlines):
        raise ValueError("You provided more --ticker values than --headline values.")
    if len(cli_sources) > len(cli_headlines):
        raise ValueError("You provided more --source values than --headline values.")

    padded_tickers = cli_tickers + [None] * (len(cli_headlines) - len(cli_tickers))
    padded_sources = cli_sources + [None] * (len(cli_headlines) - len(cli_sources))
    return [
        HeadlineInput(headline=headline, ticker=ticker, source=source)
        for headline, ticker, source in zip(cli_headlines, padded_tickers, padded_sources)
    ]


def _provider_env_var(provider_name: str) -> str:
    mapping = {
        "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
        "newsapi": "NEWSAPI_API_KEY",
    }
    return mapping[provider_name]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        headlines = load_headlines(args.file, args.headline, args.ticker, args.source)
        if args.provider:
            provider = get_provider(args.provider)
            provider_request = FetchRequest(
                ticker=args.ticker[0] if args.ticker else None,
                query=args.query,
                limit=args.limit,
            )
            headlines.extend(provider.fetch(provider_request))
    except Exception as exc:  # pragma: no cover - argparse-facing guardrail
        parser.error(str(exc))
        return 2

    if not headlines:
        parser.error("Provide at least one --headline or a --file.")
        return 2

    result = SentimentAnalyzer().analyze(headlines)
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    print(f"Overall sentiment: {result.overall_label} ({result.average_score:+.2f})")
    print(f"Confidence: {result.confidence:.2f}")
    if args.provider:
        env_hint = _provider_env_var(args.provider)
        provider_key_state = "set" if os.getenv(env_hint) else "missing"
        print(f"Live provider: {args.provider} ({env_hint} {provider_key_state})")
    print(
        "Breakdown: "
        f"{result.bullish_count} bullish, "
        f"{result.bearish_count} bearish, "
        f"{result.neutral_count} neutral"
    )
    print("")
    for item in result.headlines:
        metadata = []
        if item.ticker:
            metadata.append(f"ticker={item.ticker}")
        if item.source:
            metadata.append(f"source={item.source}")
        metadata_text = f" [{', '.join(metadata)}]" if metadata else ""
        positives = ", ".join(item.matched_positive_terms) if item.matched_positive_terms else "none"
        negatives = ", ".join(item.matched_negative_terms) if item.matched_negative_terms else "none"
        print(f"- {item.label:17} {item.score:+.2f} | {item.headline}{metadata_text}")
        print(f"  positive terms: {positives}")
        print(f"  negative terms: {negatives}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
