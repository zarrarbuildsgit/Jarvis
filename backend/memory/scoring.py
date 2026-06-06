"""Memory scoring utilities for JARVIS.

Scores are deterministic and dependency-free so they can be used before vector DB
or LLM components are available. They combine importance, recency, frequency,
confidence, and preference signals into a single ranking score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import math
import re


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_time(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


@dataclass(slots=True)
class MemoryScore:
    importance: float = 0.5
    recency: float = 0.5
    frequency: float = 0.0
    confidence: float = 0.75
    preference: float = 0.0
    relevance: float = 0.0
    final: float = 0.0
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MemoryScorer:
    """Scores memory entries for storage and retrieval."""

    HIGH_IMPORTANCE_TERMS = [
        "always", "never", "prefer", "preference", "favorite", "remember",
        "important", "critical", "password", "token", "project", "workflow",
        "my name", "call me", "use", "default",
    ]
    LOW_IMPORTANCE_TERMS = ["thanks", "thank you", "ok", "okay", "hello", "hi"]

    def score_text(self, text: str, metadata: Optional[Dict[str, Any]] = None, query: str = "") -> MemoryScore:
        metadata = metadata or {}
        text_l = text.lower().strip()
        score = MemoryScore()

        score.importance = self._importance(text_l, score.reasons)
        score.confidence = float(metadata.get("confidence", self._confidence(text_l)))
        score.frequency = self._frequency(metadata)
        score.preference = self._preference_signal(text_l, score.reasons)
        score.recency = self._recency(metadata.get("timestamp") or metadata.get("last_used") or metadata.get("created_at"))
        score.relevance = self._lexical_relevance(query, text_l) if query else 0.0
        score.final = self.combine(score)
        return score

    def combine(self, score: MemoryScore) -> float:
        final = (
            0.30 * score.importance
            + 0.20 * score.recency
            + 0.15 * score.frequency
            + 0.15 * score.confidence
            + 0.10 * score.preference
            + 0.10 * score.relevance
        )
        return round(max(0.0, min(1.0, final)), 4)

    def enrich_metadata(self, text: str, metadata: Optional[Dict[str, Any]] = None, query: str = "") -> Dict[str, Any]:
        metadata = dict(metadata or {})
        score = self.score_text(text, metadata, query)
        metadata.update({
            "importance": score.importance,
            "recency_score": score.recency,
            "frequency_score": score.frequency,
            "confidence": score.confidence,
            "preference_score": score.preference,
            "relevance_score": score.relevance,
            "memory_score": score.final,
            "score_reasons": ",".join(score.reasons),
        })
        return metadata

    def rank(self, memories: Iterable[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for memory in memories:
            doc = str(memory.get("document") or memory.get("text") or memory.get("fact") or "")
            metadata = dict(memory.get("metadata") or {})
            score = self.score_text(doc, metadata, query)
            enriched = dict(memory)
            enriched["score"] = score.to_dict()
            ranked.append(enriched)
        return sorted(ranked, key=lambda item: item["score"]["final"], reverse=True)

    def _importance(self, text: str, reasons: list[str]) -> float:
        if not text:
            return 0.0
        value = 0.45
        if len(text) > 120:
            value += 0.1
            reasons.append("detailed")
        if any(term in text for term in self.HIGH_IMPORTANCE_TERMS):
            value += 0.25
            reasons.append("high_importance_terms")
        if any(term == text or text.startswith(term + " ") for term in self.LOW_IMPORTANCE_TERMS):
            value -= 0.25
            reasons.append("smalltalk")
        if re.search(r"\b(c:\\|/[\w.-]+/|\.py|\.json|\.yaml|\.md)\b", text):
            value += 0.1
            reasons.append("path_or_file")
        return round(max(0.0, min(1.0, value)), 4)

    def _confidence(self, text: str) -> float:
        uncertainty = ["maybe", "probably", "i think", "not sure", "might"]
        if any(term in text for term in uncertainty):
            return 0.55
        return 0.82

    def _frequency(self, metadata: Dict[str, Any]) -> float:
        count = int(metadata.get("use_count", metadata.get("frequency", 0)) or 0)
        return round(min(1.0, math.log1p(count) / math.log(20)), 4) if count > 0 else 0.0

    def _preference_signal(self, text: str, reasons: list[str]) -> float:
        patterns = [r"\bi prefer\b", r"\bmy favorite\b", r"\balways use\b", r"\bdefault\b", r"\bcall me\b"]
        if any(re.search(p, text) for p in patterns):
            reasons.append("preference_signal")
            return 1.0
        return 0.0

    def _recency(self, timestamp: str | None) -> float:
        parsed = parse_time(timestamp)
        if not parsed:
            return 0.5
        age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400)
        return round(math.exp(-age_days / 30), 4)

    def _lexical_relevance(self, query: str, text: str) -> float:
        q_words = {w for w in re.findall(r"[a-zA-Z0-9_]+", query.lower()) if len(w) > 2}
        if not q_words:
            return 0.0
        t_words = set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))
        return round(len(q_words & t_words) / len(q_words), 4)
