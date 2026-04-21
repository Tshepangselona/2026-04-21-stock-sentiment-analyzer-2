from __future__ import annotations

from dataclasses import dataclass
import math
import re
from statistics import mean
from typing import Any, Iterable


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
class HeadlineInput:
    headline: str
    ticker: str | None = None
    source: str | None = None


@dataclass(slots=True)
class HeadlineAnalysis:
    headline: str
    ticker: str | None
    source: str | None
    score: float
    label: str
    matched_positive_terms: list[str]
    matched_negative_terms: list[str]

    @property
    def matched_terms(self) -> list[str]:
        return sorted(set(self.matched_positive_terms + self.matched_negative_terms))

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "ticker": self.ticker,
            "source": self.source,
            "score": self.score,
            "label": self.label,
            "matched_positive_terms": self.matched_positive_terms,
            "matched_negative_terms": self.matched_negative_terms,
            "matched_terms": self.matched_terms,
        }


@dataclass(slots=True)
class AnalysisResult:
    headline_count: int
    average_score: float
    overall_label: str
    confidence: float
    bullish_count: int
    bearish_count: int
    neutral_count: int
    strongest_bullish: HeadlineAnalysis | None
    strongest_bearish: HeadlineAnalysis | None
    headlines: list[HeadlineAnalysis]

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline_count": self.headline_count,
            "average_score": self.average_score,
            "overall_label": self.overall_label,
            "confidence": self.confidence,
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "strongest_bullish": None if self.strongest_bullish is None else self.strongest_bullish.to_dict(),
            "strongest_bearish": None if self.strongest_bearish is None else self.strongest_bearish.to_dict(),
            "headlines": [headline.to_dict() for headline in self.headlines],
        }


class SentimentAnalyzer:
    def __init__(
        self,
        positive_terms: dict[str, float] | None = None,
        negative_terms: dict[str, float] | None = None,
    ) -> None:
        self.positive_terms = positive_terms or POSITIVE_TERMS
        self.negative_terms = negative_terms or NEGATIVE_TERMS

    def analyze_headline(
        self,
        headline: str,
        ticker: str | None = None,
        source: str | None = None,
    ) -> HeadlineAnalysis:
        normalized = headline.casefold()
        matched_positive_terms: list[str] = []
        matched_negative_terms: list[str] = []
        score = 0.0

        score += self._score_phrases(normalized, self.positive_terms, matched_positive_terms)
        score += self._score_phrases(normalized, self.negative_terms, matched_negative_terms)

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
            if token_score > 0:
                matched_positive_terms.append(token)
            else:
                matched_negative_terms.append(token)

        score = max(-5.0, min(5.0, round(score, 2)))
        label = self._label_from_score(score)
        return HeadlineAnalysis(
            headline=headline,
            ticker=ticker or self._extract_ticker(headline),
            source=source,
            score=score,
            label=label,
            matched_positive_terms=sorted(set(matched_positive_terms)),
            matched_negative_terms=sorted(set(matched_negative_terms)),
        )

    def analyze(self, headlines: Iterable[str | HeadlineInput | dict[str, Any]]) -> AnalysisResult:
        analyses = [self._analyze_item(item) for item in headlines]
        average_score = round(mean(item.score for item in analyses), 2) if analyses else 0.0
        overall_label = self._label_from_score(average_score)
        confidence = self._confidence_from_scores([item.score for item in analyses])
        bullish_count = sum(1 for item in analyses if item.score > 0.35)
        bearish_count = sum(1 for item in analyses if item.score < -0.35)
        neutral_count = len(analyses) - bullish_count - bearish_count
        return AnalysisResult(
            headline_count=len(analyses),
            average_score=average_score,
            overall_label=overall_label,
            confidence=confidence,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count,
            strongest_bullish=max(analyses, key=lambda item: item.score, default=None),
            strongest_bearish=min(analyses, key=lambda item: item.score, default=None),
            headlines=analyses,
        )

    def _analyze_item(self, item: str | HeadlineInput | dict[str, Any]) -> HeadlineAnalysis:
        normalized = self._normalize_item(item)
        return self.analyze_headline(
            normalized.headline,
            ticker=normalized.ticker,
            source=normalized.source,
        )

    def _normalize_item(self, item: str | HeadlineInput | dict[str, Any]) -> HeadlineInput:
        if isinstance(item, HeadlineInput):
            return item
        if isinstance(item, str):
            return HeadlineInput(headline=item)
        if isinstance(item, dict):
            headline = item.get("headline") or item.get("title") or item.get("text")
            if not isinstance(headline, str) or not headline.strip():
                raise ValueError("Each structured headline item must include a non-empty 'headline', 'title', or 'text'.")
            ticker = item.get("ticker")
            source = item.get("source")
            return HeadlineInput(
                headline=headline,
                ticker=ticker if isinstance(ticker, str) and ticker.strip() else None,
                source=source if isinstance(source, str) and source.strip() else None,
            )
        raise TypeError(f"Unsupported headline item type: {type(item)!r}")

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

    def _extract_ticker(self, headline: str) -> str | None:
        patterns = [
            r"\$([A-Z]{1,5})\b",
            r"\(([A-Z]{1,5})\)",
            r"\b(?:NASDAQ|NYSE|AMEX):\s*([A-Z]{1,5})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, headline)
            if match:
                return match.group(1)
        return None
