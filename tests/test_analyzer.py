import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_sentiment_analyzer.analyzer import HeadlineInput, SentimentAnalyzer


class SentimentAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = SentimentAnalyzer()

    def test_positive_headline_scores_bullish(self) -> None:
        result = self.analyze("Acme stock surges after record profit beat")

        self.assertGreater(result.score, 0)
        self.assertIn(result.label, {"bullish", "slightly bullish"})
        self.assertIn("surges", result.matched_positive_terms)

    def test_negative_headline_scores_bearish(self) -> None:
        result = self.analyze("Acme plunges after fraud investigation and guidance cut")

        self.assertLess(result.score, 0)
        self.assertIn(result.label, {"bearish", "slightly bearish"})
        self.assertIn("fraud", result.matched_negative_terms)

    def test_batch_analysis_returns_average_and_confidence(self) -> None:
        result = self.analyzer.analyze(
            [
                "Bank stock rallies on strong profit growth",
                "Retailer drops after weak outlook",
            ]
        )

        self.assertEqual(len(result.headlines), 2)
        self.assertGreaterEqual(result.average_score, -5.0)
        self.assertLessEqual(result.average_score, 5.0)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)
        self.assertEqual(result.bullish_count + result.bearish_count + result.neutral_count, 2)

    def test_extracts_ticker_from_headline(self) -> None:
        result = self.analyze("Nvidia ($NVDA) surges after strong earnings")

        self.assertEqual(result.ticker, "NVDA")

    def test_accepts_structured_headlines(self) -> None:
        result = self.analyzer.analyze(
            [
                HeadlineInput(headline="Apple raises guidance after strong iPhone sales", ticker="AAPL", source="Reuters"),
                {"headline": "Tesla drops after weak deliveries", "ticker": "TSLA", "source": "Bloomberg"},
            ]
        )

        self.assertEqual(result.headline_count, 2)
        self.assertEqual(result.headlines[0].ticker, "AAPL")
        self.assertEqual(result.headlines[1].source, "Bloomberg")
        self.assertIsNotNone(result.strongest_bullish)
        self.assertIsNotNone(result.strongest_bearish)

    def analyze(self, headline: str):
        return self.analyzer.analyze_headline(headline)


if __name__ == "__main__":
    unittest.main()
