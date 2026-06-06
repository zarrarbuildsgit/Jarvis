"""Persistent delayed/recurring scheduler definitions for JARVIS."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
import json

from backend.tasks.models import ScheduledTask, ScheduleType, TaskPriority, parse_iso, utc_now_iso
from backend.tasks.queue import TaskQueue


class TaskScheduler:
    def __init__(self, schedule_file: str = "data/tasks/schedules.json", queue: TaskQueue | None = None):
        self.schedule_file = Path(schedule_file)
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        self.queue = queue or TaskQueue()
        self._schedules: Dict[str, ScheduledTask] = {}
        self.load()

    def load(self) -> None:
        if not self.schedule_file.exists():
            self._schedules = {}
            return
        try:
            data = json.loads(self.schedule_file.read_text(encoding="utf-8"))
            self._schedules = {item["id"]: ScheduledTask.from_dict(item) for item in data}
        except Exception:
            corrupt = self.schedule_file.with_suffix(".corrupt.json")
            try:
                self.schedule_file.rename(corrupt)
            except Exception:
                pass
            self._schedules = {}

    def save(self) -> None:
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.schedule_file.with_suffix(".tmp")
        tmp.write_text(json.dumps([s.to_dict() for s in self._schedules.values()], indent=2), encoding="utf-8")
        tmp.replace(self.schedule_file)

    def schedule_once(self, command: str, run_at: str, priority: str | TaskPriority = TaskPriority.NORMAL, metadata: Optional[dict] = None) -> ScheduledTask:
        scheduled = ScheduledTask(command=command, schedule_type=ScheduleType.ONCE, priority=TaskPriority(priority), next_run_at=run_at, metadata=metadata or {})
        self._schedules[scheduled.id] = scheduled
        self.save()
        return scheduled

    def schedule_delay(self, command: str, delay_seconds: int, priority: str | TaskPriority = TaskPriority.NORMAL, metadata: Optional[dict] = None) -> ScheduledTask:
        run_at = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=max(0, delay_seconds))).isoformat() + "Z"
        return self.schedule_once(command, run_at, priority, metadata)

    def schedule_interval(self, command: str, interval_seconds: int, priority: str | TaskPriority = TaskPriority.NORMAL, metadata: Optional[dict] = None) -> ScheduledTask:
        scheduled = ScheduledTask(
            command=command,
            schedule_type=ScheduleType.INTERVAL,
            priority=TaskPriority(priority),
            interval_seconds=max(1, int(interval_seconds)),
            metadata=metadata or {},
        )
        scheduled.next_run_at = scheduled.compute_next_run()
        self._schedules[scheduled.id] = scheduled
        self.save()
        return scheduled

    def schedule_daily(self, command: str, daily_time: str, priority: str | TaskPriority = TaskPriority.NORMAL, metadata: Optional[dict] = None) -> ScheduledTask:
        scheduled = ScheduledTask(command=command, schedule_type=ScheduleType.DAILY, priority=TaskPriority(priority), daily_time=daily_time, metadata=metadata or {})
        scheduled.next_run_at = scheduled.compute_next_run()
        self._schedules[scheduled.id] = scheduled
        self.save()
        return scheduled

    def list(self, enabled: bool | None = None) -> List[ScheduledTask]:
        items = list(self._schedules.values())
        if enabled is not None:
            items = [item for item in items if item.enabled == enabled]
        return sorted(items, key=lambda s: s.next_run_at or "")

    def get(self, schedule_id: str) -> Optional[ScheduledTask]:
        return self._schedules.get(schedule_id)

    def cancel(self, schedule_id: str) -> ScheduledTask:
        scheduled = self._require(schedule_id)
        scheduled.enabled = False
        scheduled.updated_at = utc_now_iso()
        self.save()
        return scheduled

    def due(self) -> List[ScheduledTask]:
        now = datetime.now(timezone.utc)
        due_items: list[ScheduledTask] = []
        for scheduled in self._schedules.values():
            if not scheduled.enabled:
                continue
            next_run = parse_iso(scheduled.next_run_at)
            if next_run and next_run <= now:
                due_items.append(scheduled)
        return sorted(due_items, key=lambda s: s.next_run_at or "")

    def enqueue_due(self) -> List[dict]:
        enqueued: list[dict] = []
        for scheduled in self.due():
            task = self.queue.add(
                scheduled.command,
                priority=scheduled.priority,
                scheduled_for=scheduled.next_run_at,
                metadata={"schedule_id": scheduled.id, **scheduled.metadata},
            )
            scheduled.last_run_at = utc_now_iso()
            scheduled.run_count += 1
            if scheduled.schedule_type == ScheduleType.ONCE:
                scheduled.enabled = False
                scheduled.next_run_at = None
            else:
                scheduled.next_run_at = scheduled.compute_next_run()
            scheduled.updated_at = utc_now_iso()
            enqueued.append({"schedule": scheduled.to_dict(), "task": task.to_dict()})
        if enqueued:
            self.save()
        return enqueued

    def _require(self, schedule_id: str) -> ScheduledTask:
        scheduled = self.get(schedule_id)
        if not scheduled:
            raise KeyError(f"Schedule not found: {schedule_id}")
        return scheduled
