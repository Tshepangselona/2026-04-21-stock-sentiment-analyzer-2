from __future__ import annotations

from dataclasses import dataclass
import math
import re
from statistics import mean


POSITIVE_TERMS = {
    "beat": 1.8,
    "beats": 1.8,
    "surge": 1.7,
    "surges": 1.7,
    "jump": 1.5,
    "jumps": 1.5,
    "rally": 1.4,
    "rallies": 1.4,
    "upgrade": 1.6,
    "upgrades": 1.6,
    "growth": 1.3,
    "profit": 1.5,
    "profits": 1.5,
    "record": 1.2,
    "strong": 1.0,
    "bullish": 1.9,
    "outperform": 1.7,
    "buyback": 1.4,
    "guidance raised": 2.1,
    "raises guidance": 2.1,
    "expands": 1.1,
    "expansion": 1.1,
    "partnership": 1.0,
    "momentum": 1.0,
}

NEGATIVE_TERMS = {
    "miss": -1.8,
    "misses": -1.8,
    "drop": -1.5,
    "drops": -1.5,
    "plunge": -2.0,
    "plunges": -2.0,
    "fall": -1.4,
    "falls": -1.4,
    "downgrade": -1.7,
    "downgrades": -1.7,
    "weak": -1.1,
    "loss": -1.7,
    "losses": -1.7,
    "bearish": -1.9,
    "investigation": -1.7,
    "lawsuit": -1.6,
    "cuts guidance": -2.2,
    "guidance cut": -2.2,
    "warning": -1.4,
    "slump": -1.6,
    "slumps": -1.6,
    "recall": -1.8,
    "fraud": -2.3,
}

AMPLIFIERS = {
    "massive": 0.4,
    "sharply": 0.3,
    "significantly": 0.3,
    "unexpectedly": 0.25,
    "record": 0.2,
}

NEGATIONS = {"not", "no", "never", "without"}


@dataclass(slots=True)
class HeadlineAnalysis:
    headline: str
    score: float
    label: str
    matched_terms: list[str]


@dataclass(slots=True)
class AnalysisResult:
    average_score: float
    overall_label: str
    confidence: float
    headlines: list[HeadlineAnalysis]


class SentimentAnalyzer:
    def __init__(
        self,
        positive_terms: dict[str, float] | None = None,
        negative_terms: dict[str, float] | None = None,
    ) -> None:
        self.positive_terms = positive_terms or POSITIVE_TERMS
        self.negative_terms = negative_terms or NEGATIVE_TERMS

    def analyze_headline(self, headline: str) -> HeadlineAnalysis:
        normalized = headline.casefold()
        matched_terms: list[str] = []
        score = 0.0

        score += self._score_phrases(normalized, self.positive_terms, matched_terms)
        score += self._score_phrases(normalized, self.negative_terms, matched_terms)

        tokens = re.findall(r"[a-z']+", normalized)
        for index, token in enumerate(tokens):
            token_score = self.positive_terms.get(token, 0.0) + self.negative_terms.get(token, 0.0)
            if token_score == 0.0:
                continue

            window = tokens[max(0, index - 2) : index]
            if any(word in NEGATIONS for word in window):
                token_score *= -0.8

            amplifier = sum(AMPLIFIERS.get(word, 0.0) for word in window)
            token_score *= 1 + amplifier

            score += token_score
            matched_terms.append(token)

        score = max(-5.0, min(5.0, round(score, 2)))
        label = self._label_from_score(score)
        return HeadlineAnalysis(
            headline=headline,
            score=score,
            label=label,
            matched_terms=sorted(set(matched_terms)),
        )

    def analyze(self, headlines: list[str]) -> AnalysisResult:
        analyses = [self.analyze_headline(headline) for headline in headlines]
        average_score = round(mean(item.score for item in analyses), 2) if analyses else 0.0
        overall_label = self._label_from_score(average_score)
        confidence = self._confidence_from_scores([item.score for item in analyses])
        return AnalysisResult(
            average_score=average_score,
            overall_label=overall_label,
            confidence=confidence,
            headlines=analyses,
        )

    def _score_phrases(
        self,
        normalized_headline: str,
        lexicon: dict[str, float],
        matched_terms: list[str],
    ) -> float:
        score = 0.0
        for term, weight in lexicon.items():
            if " " not in term:
                continue
            if term in normalized_headline:
                score += weight
                matched_terms.append(term)
        return score

    def _label_from_score(self, score: float) -> str:
        if score >= 1.5:
            return "bullish"
        if score >= 0.35:
            return "slightly bullish"
        if score <= -1.5:
            return "bearish"
        if score <= -0.35:
            return "slightly bearish"
        return "neutral"

    def _confidence_from_scores(self, scores: list[float]) -> float:
        if not scores:
            return 0.0
        avg_magnitude = mean(abs(score) for score in scores)
        agreement = 1.0 if len(scores) == 1 else 1 - min(1.0, self._stddev(scores) / 3)
        confidence = (avg_magnitude / 5.0) * 0.6 + agreement * 0.4
        return round(max(0.0, min(1.0, confidence)), 2)

    def _stddev(self, scores: list[float]) -> float:
        if len(scores) < 2:
            return 0.0
        avg = mean(scores)
        variance = sum((score - avg) ** 2 for score in scores) / len(scores)
        return math.sqrt(variance)
