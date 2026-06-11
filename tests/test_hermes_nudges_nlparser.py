"""Focused tests for backend.tasks.nl_parser and backend.memory.nudges.

All tests run offline: no GPU, no models, no network. File I/O is confined
to pytest tmp_path.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from backend.memory.nudges import MAX_FILE_CHARS, MemoryNudges
from backend.memory.preferences import PreferenceStore
from backend.tasks.nl_parser import NaturalLanguageParser


# ---------------------------------------------------------------------------
# Natural language parser
# ---------------------------------------------------------------------------

@pytest.fixture()
def parser() -> NaturalLanguageParser:
    return NaturalLanguageParser()


class TestNLParserDaily:
    def test_every_day_at_9am(self, parser):
        result = parser.parse("every day at 9am")
        assert result is not None
        assert result["type"] == "daily"
        assert result["time"] == "09:00"
        assert result["cron"] == "0 9 * * *"

    def test_every_day_at_930pm(self, parser):
        result = parser.parse("every day at 9:30pm")
        assert result["type"] == "daily"
        assert result["time"] == "21:30"
        assert result["cron"] == "30 21 * * *"

    def test_every_morning_default(self, parser):
        result = parser.parse("every morning")
        assert result["type"] == "daily"
        assert result["time"] == "09:00"

    def test_every_morning_at_7am(self, parser):
        result = parser.parse("every morning at 7am")
        assert result["type"] == "daily"
        assert result["time"] == "07:00"
        assert result["cron"] == "0 7 * * *"

    def test_every_evening_default(self, parser):
        result = parser.parse("every evening")
        assert result["type"] == "daily"
        assert result["time"] == "18:00"

    def test_every_weekday_at_8am(self, parser):
        result = parser.parse("every weekday at 8am")
        assert result["type"] == "daily"
        assert result["time"] == "08:00"
        assert result["cron"] == "0 8 * * 1-5"

    def test_noon(self, parser):
        result = parser.parse("every day at noon")
        assert result["type"] == "daily"
        assert result["time"] == "12:00"
        assert result["cron"] == "0 12 * * *"

    def test_midnight(self, parser):
        result = parser.parse("every day at midnight")
        assert result["type"] == "daily"
        assert result["time"] == "00:00"
        assert result["cron"] == "0 0 * * *"


class TestNLParserWeekly:
    def test_every_monday_at_9am(self, parser):
        result = parser.parse("every monday at 9am")
        assert result is not None
        # Regression: this used to fall through to a one-shot "at 9am" schedule
        assert result["type"] == "weekly"
        assert result["weekday"] == "monday"
        assert result["day_of_week"] == 1  # cron: 0=Sunday
        assert result["time"] == "09:00"
        assert result["cron"] == "0 9 * * 1"

    def test_every_sunday_default_time(self, parser):
        result = parser.parse("every sunday")
        assert result["type"] == "weekly"
        assert result["day_of_week"] == 0
        assert result["time"] == "09:00"

    def test_every_friday_at_530pm(self, parser):
        result = parser.parse("every friday at 5:30pm")
        assert result["type"] == "weekly"
        assert result["day_of_week"] == 5
        assert result["time"] == "17:30"
        assert result["cron"] == "30 17 * * 5"


class TestNLParserIntervalDelay:
    def test_every_30_minutes(self, parser):
        result = parser.parse("every 30 minutes")
        assert result["type"] == "interval"
        assert result["seconds"] == 1800

    def test_every_2_hours(self, parser):
        result = parser.parse("every 2 hours")
        assert result["type"] == "interval"
        assert result["seconds"] == 7200

    def test_in_30_minutes(self, parser):
        result = parser.parse("in 30 minutes")
        assert result["type"] == "delay"
        assert result["seconds"] == 1800

    def test_in_1_hour(self, parser):
        result = parser.parse("in 1 hour")
        assert result["type"] == "delay"
        assert result["seconds"] == 3600

    def test_in_2_days(self, parser):
        result = parser.parse("in 2 days")
        assert result["type"] == "delay"
        assert result["seconds"] == 2 * 86400


class TestNLParserOnce:
    def test_at_5pm_is_future_and_tz_aware(self, parser):
        result = parser.parse("at 5pm")
        assert result["type"] == "once"
        run_at = datetime.fromisoformat(result["run_at"])
        # Timezone-aware so a UTC-assuming consumer cannot shift the time
        assert run_at.tzinfo is not None
        assert run_at > datetime.now().astimezone()
        assert run_at.hour == 17
        assert run_at.minute == 0

    def test_at_12am_is_midnight(self, parser):
        result = parser.parse("at 12am")
        assert result["type"] == "once"
        run_at = datetime.fromisoformat(result["run_at"])
        assert run_at.hour == 0

    def test_at_12pm_is_noon(self, parser):
        result = parser.parse("at 12pm")
        run_at = datetime.fromisoformat(result["run_at"])
        assert run_at.hour == 12


class TestNLParserInvalid:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "hello world",
            "open chrome please",
            "every day at 13pm",   # invalid 12h hour
            "at 9:75am",           # invalid minute
            "at 0pm",              # invalid 12h hour
        ],
    )
    def test_returns_none(self, parser, text):
        assert parser.parse(text) is None

    def test_every_monday_not_parsed_as_once(self, parser):
        result = parser.parse("every monday at 9am")
        assert result["type"] != "once"


class TestNLParserExtractCommand:
    def test_extract_schedule_and_remaining(self, parser):
        schedule, remaining = parser.extract_schedule_from_command(
            "every morning at 9am check email"
        )
        assert schedule is not None
        assert schedule["type"] == "daily"
        assert schedule["time"] == "09:00"
        assert remaining == "check email"

    def test_no_schedule_returns_original(self, parser):
        schedule, remaining = parser.extract_schedule_from_command("open notepad")
        assert schedule is None
        assert remaining == "open notepad"


# ---------------------------------------------------------------------------
# Memory nudges
# ---------------------------------------------------------------------------

def _write_trajectory(
    traj_dir: Path,
    traj_id: str,
    command: str,
    *,
    success: bool = True,
    timestamp: str | None = None,
) -> None:
    traj_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "id": traj_id,
        "command": command,
        "timestamp": timestamp or (datetime.now() - timedelta(hours=1)).isoformat(),
        "plan": None,
        "steps": [
            {
                "step_number": 1,
                "timestamp": datetime.now().isoformat(),
                "thought": "",
                "action": {"type": "open_app"},
                "observation": None,
                "result": None,
            }
        ],
        "final_result": None,
        "success": success,
        "duration_ms": 120,
        "metadata": {},
    }
    (traj_dir / f"{traj_id}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )


def _make_nudges(tmp_path: Path) -> tuple[MemoryNudges, Path, Path]:
    from backend.agent.trajectory import TrajectoryLogger

    traj_dir = tmp_path / "trajectories"
    memory_dir = tmp_path / "memory"
    nudges = MemoryNudges(
        trajectory_logger=TrajectoryLogger(base_dir=str(traj_dir)),
        preference_store=PreferenceStore(str(memory_dir / "preferences.json")),
        memory_dir=memory_dir,
    )
    return nudges, traj_dir, memory_dir


class TestMemoryNudges:
    def test_no_trajectories(self, tmp_path):
        nudges, _, memory_dir = _make_nudges(tmp_path)
        result = nudges.run_daily_nudge()
        assert result == {"analyzed": 0, "insights": []}
        assert not (memory_dir / "USER.md").exists()
        assert not (memory_dir / "MEMORY.md").exists()

    def test_creates_user_and_memory_md(self, tmp_path):
        nudges, traj_dir, memory_dir = _make_nudges(tmp_path)
        _write_trajectory(traj_dir, "traj_a1", "open chrome")
        _write_trajectory(traj_dir, "traj_a2", "open chrome")
        _write_trajectory(traj_dir, "traj_a3", "play music on spotify", success=False)

        result = nudges.run_daily_nudge()
        assert "error" not in result
        assert result["analyzed"] == 3
        assert result["preferences_extracted"] >= 2

        user_md = (memory_dir / "USER.md").read_text(encoding="utf-8")
        memory_md = (memory_dir / "MEMORY.md").read_text(encoding="utf-8")
        assert "# User Profile" in user_md
        assert "# JARVIS Memory" in memory_md
        assert "Trajectories analyzed: 3" in memory_md
        assert "Frequently used: 'open chrome' (2 times)" in memory_md

    def test_preferences_actually_persisted(self, tmp_path):
        nudges, traj_dir, memory_dir = _make_nudges(tmp_path)
        _write_trajectory(traj_dir, "traj_b1", "open chrome and turn on dark mode")
        nudges.run_daily_nudge()

        store = PreferenceStore(str(memory_dir / "preferences.json"))
        values = {p.value for p in store.list()}
        assert "Uses Chrome browser" in values
        assert "Prefers dark mode" in values

    def test_no_substring_false_positives(self, tmp_path):
        nudges, traj_dir, memory_dir = _make_nudges(tmp_path)
        # "decode" and "barcode" must not trigger the VS Code preference
        _write_trajectory(traj_dir, "traj_c1", "decode the barcode image")
        nudges.run_daily_nudge()

        store = PreferenceStore(str(memory_dir / "preferences.json"))
        values = {p.value for p in store.list()}
        assert "Uses VS Code" not in values

    def test_old_trajectories_excluded(self, tmp_path):
        nudges, traj_dir, _ = _make_nudges(tmp_path)
        old = (datetime.now() - timedelta(days=5)).isoformat()
        _write_trajectory(traj_dir, "traj_d1", "old command", timestamp=old)
        _write_trajectory(traj_dir, "traj_d2", "new command")

        result = nudges.run_daily_nudge()
        assert result["analyzed"] == 1

    def test_idempotent_reruns_and_bounded_size(self, tmp_path):
        nudges, traj_dir, memory_dir = _make_nudges(tmp_path)
        long_cmd = "open chrome " + "x" * 500  # long command must be truncated
        for i in range(3):
            _write_trajectory(traj_dir, f"traj_e{i}", long_cmd)

        sizes = []
        for _ in range(25):
            result = nudges.run_daily_nudge()
            assert "error" not in result
            sizes.append((memory_dir / "MEMORY.md").stat().st_size)

        user_md = (memory_dir / "USER.md").read_text(encoding="utf-8")
        memory_md = (memory_dir / "MEMORY.md").read_text(encoding="utf-8")

        # Bounded: never exceeds the hard cap and stabilizes instead of growing
        assert all(size <= MAX_FILE_CHARS for size in sizes)
        assert sizes[-1] == sizes[-2] == sizes[-3]

        # Idempotent structure: single header, at most one History section
        assert memory_md.count("# JARVIS Memory") == 1
        assert memory_md.count("## History") <= 1
        assert user_md.count("# User Profile") == 1

    def test_get_user_profile(self, tmp_path):
        nudges, traj_dir, _ = _make_nudges(tmp_path)
        _write_trajectory(traj_dir, "traj_f1", "open chrome")
        nudges.run_daily_nudge()

        profile = nudges.get_user_profile()
        assert profile["user_md_exists"] is True
        assert profile["memory_md_exists"] is True
        assert "user_md_preview" in profile
