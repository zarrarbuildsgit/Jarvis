"""Browser and external-integration actions.

External send/post operations are draft-only. JARVIS must never send messages,
emails, or posts directly without an explicit approval flow in a future sprint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
import json

from backend.browser.session import BrowserResult, BrowserSession
from backend.memory.summarizer import MemorySummarizer


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class ExternalDraft:
    kind: str
    recipient: str
    subject: str = ""
    body: str = ""
    id: str = field(default_factory=lambda: f"draft_{uuid4().hex[:12]}")
    status: str = "draft"
    created_at: str = field(default_factory=now_iso)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExternalDraft":
        return cls(**dict(data))


class ExternalDraftStore:
    def __init__(self, path: str = "data/integrations/drafts.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._drafts: Dict[str, ExternalDraft] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._drafts = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._drafts = {item["id"]: ExternalDraft.from_dict(item) for item in data}
        except Exception:
            self._drafts = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([d.to_dict() for d in self._drafts.values()], indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def create(self, kind: str, recipient: str, body: str, subject: str = "", metadata: Optional[Dict[str, Any]] = None) -> ExternalDraft:
        draft = ExternalDraft(kind=kind, recipient=recipient, subject=subject, body=body, metadata=metadata or {})
        self._drafts[draft.id] = draft
        self.save()
        return draft

    def list(self, status: str | None = None) -> List[ExternalDraft]:
        drafts = list(self._drafts.values())
        if status:
            drafts = [draft for draft in drafts if draft.status == status]
        return sorted(drafts, key=lambda d: d.created_at, reverse=True)

    def get(self, draft_id: str) -> Optional[ExternalDraft]:
        return self._drafts.get(draft_id)


class BrowserActions:
    def __init__(self, session: BrowserSession | None = None, draft_store: ExternalDraftStore | None = None):
        self.session = session or BrowserSession()
        self.drafts = draft_store or ExternalDraftStore()
        self.summarizer = MemorySummarizer()

    def open_url(self, url: str) -> BrowserResult:
        return self.session.open_url(url)

    def search(self, query: str, engine: str = "google") -> BrowserResult:
        return self.session.search(query, engine)

    def read_and_summarize(self, url: str, max_chars: int = 5000) -> BrowserResult:
        result = self.session.read_url(url, max_chars=max_chars)
        if not result.success:
            return result
        summary = self.summarizer.summarize_texts([result.text], max_items=6, max_chars=900)
        result.metadata["summary"] = summary
        result.message = f"Read and summarized: {url}"
        return result

    def draft_message(self, kind: str, recipient: str, body: str, subject: str = "") -> ExternalDraft:
        return self.drafts.create(kind=kind, recipient=recipient, body=body, subject=subject, metadata={"policy": "draft_only_requires_approval_to_send"})
