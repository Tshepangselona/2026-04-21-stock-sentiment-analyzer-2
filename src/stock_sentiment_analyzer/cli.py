from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from stock_sentiment_analyzer.analyzer import SentimentAnalyzer


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
    return parser


def load_headlines(file_path: Path | None, cli_headlines: list[str]) -> list[str]:
    headlines = list(cli_headlines)
    if file_path is None:
        return headlines

    payload = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        headlines.extend(str(item) for item in payload)
    elif isinstance(payload, dict) and isinstance(payload.get("headlines"), list):
        headlines.extend(str(item) for item in payload["headlines"])
    else:
        raise ValueError("JSON must be a list of headlines or an object with a 'headlines' list.")
    return headlines


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        headlines = load_headlines(args.file, args.headline)
    except Exception as exc:  # pragma: no cover - argparse-facing guardrail
        parser.error(str(exc))
        return 2

    if not headlines:
        parser.error("Provide at least one --headline or a --file.")
        return 2

    result = SentimentAnalyzer().analyze(headlines)
    print(f"Overall sentiment: {result.overall_label} ({result.average_score:+.2f})")
    print(f"Confidence: {result.confidence:.2f}")
    print("")
    for item in result.headlines:
        matches = ", ".join(item.matched_terms) if item.matched_terms else "none"
        print(f"- {item.label:17} {item.score:+.2f} | {item.headline}")
        print(f"  matched terms: {matches}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
