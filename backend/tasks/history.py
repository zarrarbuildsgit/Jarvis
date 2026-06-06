"""Append-only task history."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"


@dataclass(slots=True)
class TaskHistoryEvent:
    task_id: str
    event_type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TaskHistory:
    def __init__(self, history_file: str = "data/tasks/history.jsonl"):
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def record(self, task_id: str, event_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> TaskHistoryEvent:
        event = TaskHistoryEvent(task_id=task_id, event_type=event_type, message=message, data=data or {})
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def tail(self, limit: int = 100, task_id: str | None = None) -> List[Dict[str, Any]]:
        if not self.history_file.exists():
            return []
        rows = self.history_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        events: list[dict[str, Any]] = []
        for line in rows:
            try:
                event = json.loads(line)
            except Exception:
                continue
            if task_id is None or event.get("task_id") == task_id:
                events.append(event)
        return events[-max(1, min(limit, 1000)):]
