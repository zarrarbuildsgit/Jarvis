"""Typed action schema for the JARVIS runtime.

Sprint 1 purpose:
- turn loose natural-language commands into structured actions
- keep executor/planner contracts stable
- make future safety policy, approval, dashboard, voice, and skills use the same format
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ActionType(str, Enum):
    """Supported deterministic runtime actions.

    New action types should be added here before executor support is added.
    This prevents ad-hoc stringly-typed tool calls spreading through the app.
    """

    NOOP = "noop"
    RESPOND = "respond"
    STATUS = "status"
    LIST_PLUGINS = "list_plugins"

    RUN_TERMINAL = "run_terminal"
    OPEN_APP = "open_app"
    LIST_WINDOWS = "list_windows"
    FOCUS_WINDOW = "focus_window"
    LIST_PROCESSES = "list_processes"
    GET_CLIPBOARD = "get_clipboard"
    SET_CLIPBOARD = "set_clipboard"
    PASTE_CLIPBOARD = "paste_clipboard"

    LIST_FILES = "list_files"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"

    ANALYZE_SCREEN = "analyze_screen"
    CLICK = "click"
    TYPE_TEXT = "type_text"
    PRESS_KEY = "press_key"

class ActionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass(slots=True)
class Action:
    """One executable step in a plan."""

    type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    id: str = field(default_factory=lambda: f"act_{uuid4().hex[:10]}")
    required_trust: int = 1
    timeout_seconds: float = 30.0
    verify: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["type"] = self.type.value
        return data


@dataclass(slots=True)
class ActionResult:
    """Result of a single action execution."""

    action_id: str
    action_type: ActionType
    status: ActionStatus
    message: str = ""
    output: Any = None
    error: Optional[str] = None
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == ActionStatus.SUCCESS

    def finish(self, status: ActionStatus, message: str = "", output: Any = None, error: Optional[str] = None) -> "ActionResult":
        self.status = status
        self.message = message
        self.output = output
        self.error = error
        self.ended_at = datetime.now().isoformat()
        return self

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["action_type"] = self.action_type.value
        data["status"] = self.status.value
        return data


@dataclass(slots=True)
class ActionPlan:
    """Structured plan generated from a user command."""

    command: str
    actions: List[Action] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"plan_{uuid4().hex[:10]}")
    summary: str = ""
    source: str = "deterministic"
    confidence: float = 0.0
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return len(self.actions) == 0

    @property
    def max_required_trust(self) -> int:
        return max((a.required_trust for a in self.actions), default=1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "summary": self.summary,
            "source": self.source,
            "confidence": self.confidence,
            "requires_confirmation": self.requires_confirmation,
            "max_required_trust": self.max_required_trust,
            "actions": [a.to_dict() for a in self.actions],
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class RuntimeResult:
    """End-to-end result of planning and executing a command."""

    command: str
    handled: bool
    success: bool
    message: str
    plan: Optional[ActionPlan] = None
    results: List[ActionResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "handled": self.handled,
            "success": self.success,
            "message": self.message,
            "plan": self.plan.to_dict() if self.plan else None,
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }
