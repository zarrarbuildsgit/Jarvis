"""Append-only JSONL audit log for JARVIS actions and policy decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json


@dataclass(slots=True)
class AuditEvent:
    event_type: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditLogger:
    def __init__(self, log_file: str = "data/security/audit.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, message: str, data: Optional[Dict[str, Any]] = None) -> AuditEvent:
        event = AuditEvent(event_type=event_type, message=message, data=data or {})
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def record_policy(self, decision, action=None, command: str = "") -> AuditEvent:
        data = {
            "decision": decision.to_dict() if hasattr(decision, "to_dict") else decision,
            "action": action.to_dict() if hasattr(action, "to_dict") else action,
            "command": command,
        }
        return self.record("policy_decision", data["decision"].get("reason", "Policy decision"), data)

    def record_action_result(self, result, action=None, command: str = "") -> AuditEvent:
        success = getattr(result, "success", False)
        data = {
            "result": result.to_dict() if hasattr(result, "to_dict") else result,
            "action": action.to_dict() if hasattr(action, "to_dict") else action,
            "command": command,
        }
        return self.record("action_result", "Action succeeded" if success else "Action failed", data)

    def tail(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.log_file.exists():
            return []
        lines = self.log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-limit:]
        events: list[dict[str, Any]] = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except Exception:
                continue
        return events
