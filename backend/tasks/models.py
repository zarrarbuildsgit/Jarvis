"""Task models for JARVIS queue and scheduler."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z"


def parse_iso(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    text = value[:-1] if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    @property
    def weight(self) -> int:
        return {
            TaskPriority.LOW: 10,
            TaskPriority.NORMAL: 20,
            TaskPriority.HIGH: 30,
            TaskPriority.URGENT: 40,
        }[self]


class ScheduleType(str, Enum):
    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"
    WEEKLY = "weekly"


# Python datetime.weekday() convention: Monday=0 ... Sunday=6
WEEKDAY_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


@dataclass(slots=True)
class Task:
    command: str
    priority: TaskPriority = TaskPriority.NORMAL
    id: str = field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    status: TaskStatus = TaskStatus.QUEUED
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    scheduled_for: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0
    result: str = ""
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_terminal(self) -> bool:
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}

    @property
    def is_due(self) -> bool:
        due_at = parse_iso(self.scheduled_for)
        return due_at is None or due_at <= datetime.now(timezone.utc)

    def mark(self, status: TaskStatus, *, result: str = "", error: str = "", progress: Optional[int] = None) -> None:
        self.status = status
        self.updated_at = utc_now_iso()
        if progress is not None:
            self.progress = max(0, min(100, int(progress)))
        if result:
            self.result = result
        if error:
            self.error = error
        if status == TaskStatus.RUNNING and not self.started_at:
            self.started_at = utc_now_iso()
        if status in {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            self.completed_at = utc_now_iso()
            if progress is None and status == TaskStatus.COMPLETED:
                self.progress = 100

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["priority"] = self.priority.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        clean = dict(data)
        clean["priority"] = TaskPriority(clean.get("priority", TaskPriority.NORMAL))
        clean["status"] = TaskStatus(clean.get("status", TaskStatus.QUEUED))
        return cls(**clean)


@dataclass(slots=True)
class ScheduledTask:
    command: str
    schedule_type: ScheduleType
    priority: TaskPriority = TaskPriority.NORMAL
    id: str = field(default_factory=lambda: f"sched_{uuid4().hex[:12]}")
    enabled: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    next_run_at: Optional[str] = None
    interval_seconds: Optional[int] = None
    daily_time: Optional[str] = None  # HH:MM, local machine time when interpreted
    weekday: Optional[str] = None  # lowercase day name, for WEEKLY schedules
    last_run_at: Optional[str] = None
    run_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["schedule_type"] = self.schedule_type.value
        data["priority"] = self.priority.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledTask":
        clean = dict(data)
        clean["schedule_type"] = ScheduleType(clean.get("schedule_type", ScheduleType.ONCE))
        clean["priority"] = TaskPriority(clean.get("priority", TaskPriority.NORMAL))
        return cls(**clean)

    def compute_next_run(self) -> Optional[str]:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        if self.schedule_type == ScheduleType.ONCE:
            return None
        if self.schedule_type == ScheduleType.INTERVAL and self.interval_seconds:
            return (now + timedelta(seconds=max(1, int(self.interval_seconds)))).isoformat() + "Z"
        if self.schedule_type == ScheduleType.DAILY and self.daily_time:
            # daily_time is local machine time; compute locally, store as UTC
            hour, minute = [int(part) for part in self.daily_time.split(":", 1)]
            local_now = datetime.now().astimezone().replace(microsecond=0)
            candidate = local_now.replace(hour=hour, minute=minute, second=0)
            if candidate <= local_now:
                candidate += timedelta(days=1)
            return candidate.astimezone(timezone.utc).isoformat() + "Z"
        if self.schedule_type == ScheduleType.WEEKLY and self.daily_time and self.weekday:
            target = WEEKDAY_INDEX.get(self.weekday.lower())
            if target is None:
                return None
            hour, minute = [int(part) for part in self.daily_time.split(":", 1)]
            local_now = datetime.now().astimezone().replace(microsecond=0)
            days_ahead = (target - local_now.weekday()) % 7
            candidate = (local_now + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0)
            if candidate <= local_now:
                candidate += timedelta(days=7)
            return candidate.astimezone(timezone.utc).isoformat() + "Z"
        return None
