"""User preference extraction and storage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import re
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class UserPreference:
    key: str
    value: str
    category: str = "general"
    confidence: float = 0.75
    source: str = "unknown"
    id: str = field(default_factory=lambda: f"pref_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    use_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.use_count += 1
        self.updated_at = now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreference":
        return cls(**dict(data))


class PreferenceExtractor:
    """Extracts explicit user preferences from natural language."""

    PATTERNS = [
        ("preferred_browser", r"\bi prefer (chrome|edge|firefox|brave|opera)\b"),
        ("preferred_browser", r"\balways use (chrome|edge|firefox|brave|opera)\b"),
        ("preferred_name", r"\bcall me ([a-zA-Z0-9_ -]{2,40})\b"),
        ("preferred_editor", r"\bi prefer (vs code|vscode|visual studio code|pycharm|notepad\+\+)\b"),
        ("default_project", r"\bmy (?:main|default) project is ([\w .:/\\-]{2,120})"),
        ("preference", r"\bi like ([\w .:/\\-]{2,120})"),
        ("preference", r"\bi don't like ([\w .:/\\-]{2,120})"),
    ]

    def extract(self, text: str, source: str = "conversation") -> List[UserPreference]:
        text_clean = " ".join(text.strip().split())
        lower = text_clean.lower()
        prefs: list[UserPreference] = []
        for key, pattern in self.PATTERNS:
            match = re.search(pattern, lower, flags=re.IGNORECASE)
            if match:
                value = match.group(1).strip(" .")
                category = key.replace("preferred_", "").replace("default_", "")
                prefs.append(UserPreference(key=key, value=value, category=category, confidence=0.86, source=source, metadata={"text": text_clean}))
        return prefs


class PreferenceStore:
    """JSON-backed preference store."""

    def __init__(self, path: str = "data/memory/preferences.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prefs: Dict[str, UserPreference] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._prefs = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._prefs = {item["key"]: UserPreference.from_dict(item) for item in data}
        except Exception:
            corrupt = self.path.with_suffix(".corrupt.json")
            try:
                self.path.rename(corrupt)
            except Exception:
                pass
            self._prefs = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([pref.to_dict() for pref in self._prefs.values()], indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(self, preference: UserPreference) -> UserPreference:
        existing = self._prefs.get(preference.key)
        if existing:
            existing.value = preference.value
            existing.category = preference.category
            existing.confidence = max(existing.confidence, preference.confidence)
            existing.source = preference.source
            existing.updated_at = now_iso()
            existing.metadata.update(preference.metadata)
            existing.touch()
            saved = existing
        else:
            self._prefs[preference.key] = preference
            saved = preference
        self.save()
        return saved

    def ingest_text(self, text: str, source: str = "conversation") -> List[UserPreference]:
        extracted = PreferenceExtractor().extract(text, source)
        return [self.upsert(pref) for pref in extracted]

    def get(self, key: str) -> Optional[UserPreference]:
        pref = self._prefs.get(key)
        if pref:
            pref.touch()
            self.save()
        return pref

    def list(self, category: str | None = None) -> List[UserPreference]:
        prefs = list(self._prefs.values())
        if category:
            prefs = [pref for pref in prefs if pref.category == category]
        return sorted(prefs, key=lambda p: (p.category, p.key))

    def as_context(self) -> str:
        if not self._prefs:
            return ""
        lines = [f"- {pref.key}: {pref.value} (confidence {pref.confidence:.2f})" for pref in self.list()]
        return "Known user preferences:\n" + "\n".join(lines)
