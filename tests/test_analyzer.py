import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stock_sentiment_analyzer.analyzer import SentimentAnalyzer


class SentimentAnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = SentimentAnalyzer()

    def test_positive_headline_scores_bullish(self) -> None:
        result = self.analyze("Acme stock surges after record profit beat")

        self.assertGreater(result.score, 0)
        self.assertIn(result.label, {"bullish", "slightly bullish"})
        self.assertIn("surges", result.matched_terms)

    def test_negative_headline_scores_bearish(self) -> None:
        result = self.analyze("Acme plunges after fraud investigation and guidance cut")

        self.assertLess(result.score, 0)
        self.assertIn(result.label, {"bearish", "slightly bearish"})
        self.assertIn("fraud", result.matched_terms)

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

    def analyze(self, headline: str):
        return self.analyzer.analyze_headline(headline)


if __name__ == "__main__":
    unittest.main()
