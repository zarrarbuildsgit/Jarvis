"""Skill/macro schema for JARVIS.

Skills are reusable workflows made from Sprint 1 structured actions. They are
stored as editable JSON so users can teach JARVIS personal routines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.agent.action_schema import Action, ActionType


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class SkillStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    DRAFT = "draft"


@dataclass(slots=True)
class SkillStep:
    action: Action
    name: str = ""
    delay_after_seconds: float = 0.0
    optional: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "action": self.action.to_dict(),
            "delay_after_seconds": self.delay_after_seconds,
            "optional": self.optional,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillStep":
        action_data = dict(data.get("action", {}))
        action_type = ActionType(action_data.get("type", ActionType.NOOP))
        action = Action(
            type=action_type,
            parameters=action_data.get("parameters", {}) or {},
            description=action_data.get("description", ""),
            id=action_data.get("id", f"act_{uuid4().hex[:10]}"),
            required_trust=int(action_data.get("required_trust", 1)),
            timeout_seconds=float(action_data.get("timeout_seconds", 30.0)),
            verify=bool(action_data.get("verify", False)),
            metadata=action_data.get("metadata", {}) or {},
        )
        return cls(
            action=action,
            name=str(data.get("name", "")),
            delay_after_seconds=float(data.get("delay_after_seconds", 0.0)),
            optional=bool(data.get("optional", False)),
            notes=str(data.get("notes", "")),
        )


@dataclass(slots=True)
class Skill:
    name: str
    description: str = ""
    trigger_phrases: List[str] = field(default_factory=list)
    steps: List[SkillStep] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"skill_{uuid4().hex[:12]}")
    status: SkillStatus = SkillStatus.ENABLED
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    run_count: int = 0
    last_run_at: Optional[str] = None
    required_trust: int = 1
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, command: str) -> bool:
        normalized = " ".join(command.lower().strip().split())
        if not normalized or self.status != SkillStatus.ENABLED:
            return False
        if normalized == self.name.lower().strip():
            return True
        return any(normalized == phrase.lower().strip() or phrase.lower().strip() in normalized for phrase in self.trigger_phrases)

    def touch_run(self) -> None:
        self.run_count += 1
        self.last_run_at = now_iso()
        self.updated_at = now_iso()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["steps"] = [step.to_dict() for step in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        clean = dict(data)
        clean["status"] = SkillStatus(clean.get("status", SkillStatus.ENABLED))
        clean["steps"] = [SkillStep.from_dict(step) for step in clean.get("steps", [])]
        return cls(**clean)
