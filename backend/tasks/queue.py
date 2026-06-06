"""Persistent task queue for JARVIS."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional
import json

from backend.tasks.history import TaskHistory
from backend.tasks.models import Task, TaskPriority, TaskStatus, utc_now_iso


class TaskQueue:
    """Small JSON-backed task queue.

    It is intentionally process-simple for local JARVIS. API/headless agent can
    share task state through `data/tasks/tasks.json`.
    """

    def __init__(self, queue_file: str = "data/tasks/tasks.json", history: TaskHistory | None = None):
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.history = history or TaskHistory()
        self._tasks: Dict[str, Task] = {}
        self.load()

    def load(self) -> None:
        if not self.queue_file.exists():
            self._tasks = {}
            return
        try:
            data = json.loads(self.queue_file.read_text(encoding="utf-8"))
            self._tasks = {item["id"]: Task.from_dict(item) for item in data}
        except Exception:
            corrupt = self.queue_file.with_suffix(".corrupt.json")
            try:
                self.queue_file.rename(corrupt)
            except Exception:
                pass
            self._tasks = {}

    def save(self) -> None:
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.queue_file.with_suffix(".tmp")
        items = [task.to_dict() for task in self._tasks.values()]
        tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
        tmp.replace(self.queue_file)

    def add(self, command: str, priority: str | TaskPriority = TaskPriority.NORMAL, scheduled_for: str | None = None, metadata: Optional[dict] = None) -> Task:
        task = Task(command=command, priority=TaskPriority(priority), scheduled_for=scheduled_for, metadata=metadata or {})
        self._tasks[task.id] = task
        self.save()
        self.history.record(task.id, "created", f"Task queued: {command}", task.to_dict())
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list(self, status: str | TaskStatus | None = None) -> List[Task]:
        tasks = list(self._tasks.values())
        if status is not None:
            status_enum = TaskStatus(status)
            tasks = [task for task in tasks if task.status == status_enum]
        return sorted(tasks, key=lambda t: (-t.priority.weight, t.scheduled_for or "", t.created_at))

    def next_due(self) -> Optional[Task]:
        candidates = [task for task in self._tasks.values() if task.status == TaskStatus.QUEUED and task.is_due]
        if not candidates:
            return None
        return sorted(candidates, key=lambda t: (-t.priority.weight, t.scheduled_for or "", t.created_at))[0]

    def mark_running(self, task_id: str) -> Task:
        return self.update(task_id, status=TaskStatus.RUNNING, progress=5, event_type="started", message="Task started")

    def complete(self, task_id: str, result: str = "") -> Task:
        return self.update(task_id, status=TaskStatus.COMPLETED, progress=100, result=result, event_type="completed", message="Task completed")

    def fail(self, task_id: str, error: str = "") -> Task:
        return self.update(task_id, status=TaskStatus.FAILED, error=error, event_type="failed", message="Task failed")

    def cancel(self, task_id: str, reason: str = "Cancelled") -> Task:
        return self.update(task_id, status=TaskStatus.CANCELLED, error=reason, event_type="cancelled", message=reason)

    def pause(self, task_id: str) -> Task:
        return self.update(task_id, status=TaskStatus.PAUSED, event_type="paused", message="Task paused")

    def resume(self, task_id: str) -> Task:
        return self.update(task_id, status=TaskStatus.QUEUED, event_type="resumed", message="Task resumed")

    def update(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        progress: int | None = None,
        result: str = "",
        error: str = "",
        event_type: str = "updated",
        message: str = "Task updated",
    ) -> Task:
        task = self._require(task_id)
        if status is not None:
            task.mark(status, result=result, error=error, progress=progress)
        else:
            task.updated_at = utc_now_iso()
            if progress is not None:
                task.progress = max(0, min(100, int(progress)))
            if result:
                task.result = result
            if error:
                task.error = error
        self.save()
        self.history.record(task.id, event_type, message, task.to_dict())
        return task

    def prune_terminal(self, keep_last: int = 200) -> int:
        terminal = [task for task in self._tasks.values() if task.is_terminal]
        terminal = sorted(terminal, key=lambda t: t.completed_at or t.updated_at or t.created_at)
        remove = terminal[:-keep_last] if len(terminal) > keep_last else []
        for task in remove:
            self._tasks.pop(task.id, None)
        if remove:
            self.save()
        return len(remove)

    def _require(self, task_id: str) -> Task:
        task = self.get(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")
        return task
