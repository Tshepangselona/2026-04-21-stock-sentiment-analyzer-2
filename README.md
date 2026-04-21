# Stock Sentiment Analyzer

A lightweight Python project that scores stock-related news headlines as bullish, bearish, or neutral using a finance-focused sentiment lexicon.

## What it does

- Scores individual headlines and batches of headlines
- Uses finance-specific terms like `beats`, `cuts guidance`, `buyback`, and `fraud`
- Accepts plain headlines or structured records with optional `ticker` and `source`
- Returns an overall sentiment label, confidence score, and bullish/bearish breakdown
- Includes sample data and a small test suite

## Quick start

```bash
$env:PYTHONPATH="src"
python -m stock_sentiment_analyzer.cli --file data/sample_headlines.json
```

Or pass headlines directly:

```bash
python -m stock_sentiment_analyzer.cli --headline "Microsoft rallies after strong cloud growth" --ticker MSFT --source Reuters --headline "Chipmaker drops on weak guidance" --ticker AMD --source Bloomberg
```

Machine-readable output:

```bash
python -m stock_sentiment_analyzer.cli --file data/sample_headlines.json --format json
```

Run the tests:

```bash
python -m unittest discover -s tests -v
```

## Project structure

```text
src/stock_sentiment_analyzer/
  analyzer.py   Core scoring logic
  cli.py        Command-line interface
data/
  sample_headlines.json
tests/
  test_analyzer.py
```

## How scoring works

The analyzer combines:

1. Weighted finance phrases such as `raises guidance` or `guidance cut`
2. Weighted single-word signals such as `surges`, `profit`, `lawsuit`, or `downgrade`
3. Small adjustments for nearby amplifiers like `sharply`
4. Basic negation handling for patterns like `not strong`

This is a practical rule-based baseline, which makes it easy to inspect and extend. The current version also detects ticker symbols in headlines like `$NVDA` and preserves ticker/source metadata from structured input.
