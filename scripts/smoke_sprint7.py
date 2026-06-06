"""Sprint 7 smoke checks.

Run with:
    uv run python scripts/smoke_sprint7.py

Validates persistent task queue, cancellation/pause/resume, task history,
delayed schedules, interval rescheduling, and restart persistence.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.tasks import TaskHistory, TaskQueue, TaskScheduler, TaskStatus


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        history = TaskHistory(str(root / "history.jsonl"))
        queue = TaskQueue(str(root / "tasks.json"), history=history)

        low = queue.add("low task", priority="low")
        high = queue.add("high task", priority="high")
        assert_true(queue.next_due().id == high.id, "priority ordering")

        queue.mark_running(high.id)
        assert_true(queue.get(high.id).status == TaskStatus.RUNNING, "mark running")
        queue.complete(high.id, "done")
        assert_true(queue.get(high.id).status == TaskStatus.COMPLETED, "complete task")
        assert_true(queue.get(high.id).progress == 100, "complete progress")

        queue.pause(low.id)
        assert_true(queue.get(low.id).status == TaskStatus.PAUSED, "pause task")
        queue.resume(low.id)
        assert_true(queue.get(low.id).status == TaskStatus.QUEUED, "resume task")
        queue.cancel(low.id, "test cancel")
        assert_true(queue.get(low.id).status == TaskStatus.CANCELLED, "cancel task")

        events = history.tail(20)
        assert_true(any(e["event_type"] == "completed" for e in events), "history records completion")
        assert_true(any(e["event_type"] == "cancelled" for e in events), "history records cancellation")

        # Persistence across queue instances.
        reloaded = TaskQueue(str(root / "tasks.json"), history=history)
        assert_true(reloaded.get(high.id).status == TaskStatus.COMPLETED, "queue persists completed task")

        scheduler = TaskScheduler(str(root / "schedules.json"), queue=reloaded)
        due = scheduler.schedule_delay("delayed task", delay_seconds=0)
        enqueued = scheduler.enqueue_due()
        assert_true(len(enqueued) == 1, "due schedule enqueued")
        assert_true(scheduler.get(due.id).enabled is False, "one-time schedule disabled after enqueue")

        interval = scheduler.schedule_interval("interval task", interval_seconds=60)
        # Force it due without sleeping.
        scheduler.get(interval.id).next_run_at = "2000-01-01T00:00:00Z"
        scheduler.save()
        enqueued_interval = scheduler.enqueue_due()
        assert_true(len(enqueued_interval) == 1, "interval schedule enqueued")
        assert_true(scheduler.get(interval.id).enabled is True, "interval remains enabled")
        assert_true(scheduler.get(interval.id).next_run_at is not None, "interval rescheduled")

    print("✅ Sprint 7 smoke checks passed")


if __name__ == "__main__":
    main()
