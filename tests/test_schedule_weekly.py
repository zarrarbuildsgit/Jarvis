"""Tests for weekly schedules and local-time daily schedule computation."""

from datetime import datetime, timedelta

import pytest

from backend.tasks.models import ScheduledTask, ScheduleType, parse_iso
from backend.tasks.scheduler import TaskScheduler


def _local(dt_utc):
    return dt_utc.astimezone()


def test_daily_next_run_uses_local_time():
    schedule = ScheduledTask(command="test", schedule_type=ScheduleType.DAILY, daily_time="09:30")
    next_run = parse_iso(schedule.compute_next_run())
    assert next_run is not None
    local = _local(next_run)
    assert (local.hour, local.minute) == (9, 30)
    delta = local - datetime.now().astimezone()
    assert timedelta(0) < delta <= timedelta(days=1)


def test_weekly_next_run_lands_on_requested_weekday():
    schedule = ScheduledTask(
        command="test", schedule_type=ScheduleType.WEEKLY, weekday="monday", daily_time="09:00"
    )
    next_run = parse_iso(schedule.compute_next_run())
    assert next_run is not None
    local = _local(next_run)
    assert local.weekday() == 0  # Monday
    assert (local.hour, local.minute) == (9, 0)
    delta = local - datetime.now().astimezone()
    assert timedelta(0) < delta <= timedelta(days=7)


def test_weekly_invalid_weekday_returns_none():
    schedule = ScheduledTask(
        command="test", schedule_type=ScheduleType.WEEKLY, weekday="someday", daily_time="09:00"
    )
    assert schedule.compute_next_run() is None


def test_scheduler_weekly_round_trip(tmp_path):
    scheduler = TaskScheduler(schedule_file=str(tmp_path / "schedules.json"))
    created = scheduler.schedule_weekly("backup files", "Friday", "18:00")
    assert created.weekday == "friday"
    assert created.next_run_at is not None

    reloaded = TaskScheduler(schedule_file=str(tmp_path / "schedules.json"))
    fetched = reloaded.get(created.id)
    assert fetched is not None
    assert fetched.schedule_type == ScheduleType.WEEKLY
    assert fetched.weekday == "friday"
    assert fetched.daily_time == "18:00"


def test_scheduler_weekly_invalid_weekday_raises(tmp_path):
    scheduler = TaskScheduler(schedule_file=str(tmp_path / "schedules.json"))
    with pytest.raises(ValueError):
        scheduler.schedule_weekly("backup files", "blursday", "18:00")
