"""Offline tests for the JARVIS skill-learning subsystem.

Covers:
- TrajectoryLogger start/log_step/finish lifecycle, persistence, get_stats
- SkillCurator pattern detection from synthetic trajectories
- SkillImprover record/get_performance round-trip
- AutonomousCreator validation logic

All tests use tmp_path for data directories: no GPU, no models, no network.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent.action_schema import Action, ActionType, RuntimeResult
from backend.agent.trajectory import TrajectoryLogger
from backend.skills.autonomous_creator import AutonomousCreator
from backend.skills.curator import CommandPattern, SkillCurator
from backend.skills.improver import SkillImprover
from backend.skills.skill_manager import SkillManager
from backend.tasks.history import TaskHistory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_result(command: str = "open notepad", success: bool = True) -> RuntimeResult:
    return RuntimeResult(
        command=command,
        handled=True,
        success=success,
        message="ok" if success else "failed",
    )


def write_trajectory_file(base_dir, idx: int, command: str, timestamp: str,
                          success: bool = True, steps=None, duration_ms: int = 50):
    """Write a synthetic individual trajectory JSON file the way the logger does."""
    traj = {
        "id": f"traj_synthetic{idx:04d}",
        "command": command,
        "timestamp": timestamp,
        "plan": None,
        "steps": steps or [],
        "final_result": {"message": "ok"},
        "success": success,
        "duration_ms": duration_ms,
        "metadata": {},
    }
    path = base_dir / f"{traj['id']}.json"
    path.write_text(json.dumps(traj), encoding="utf-8")
    return traj


def make_curator(tmp_path, **kwargs) -> SkillCurator:
    traj_dir = tmp_path / "trajectories"
    logger = TrajectoryLogger(base_dir=str(traj_dir))
    history = TaskHistory(history_file=str(tmp_path / "tasks" / "history.jsonl"))
    return SkillCurator(
        trajectory_logger=logger,
        task_history=history,
        data_dir=str(tmp_path / "skills"),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# TrajectoryLogger
# ---------------------------------------------------------------------------

class TestTrajectoryLogger:
    def test_start_step_finish_lifecycle(self, tmp_path):
        tl = TrajectoryLogger(base_dir=str(tmp_path / "traj"))
        tid = tl.start("open notepad", metadata={"trust_level": 1})
        assert tid.startswith("traj_")
        assert tl.current_trajectory is not None

        tl.log_step(thought="planning", action={"type": "open_app"})
        tl.log_step(thought="done", observation={"output": "ok"})

        traj = tl.finish(make_result("open notepad", success=True))
        assert traj is not None
        assert traj.id == tid
        assert traj.success is True
        assert traj.duration_ms >= 0
        assert [s.step_number for s in traj.steps] == [1, 2]
        # logger reset after finish
        assert tl.current_trajectory is None
        assert tl.start_time is None

    def test_finish_persists_individual_json_and_daily_jsonl(self, tmp_path):
        base = tmp_path / "traj"
        tl = TrajectoryLogger(base_dir=str(base))
        tid = tl.start("open notepad")
        tl.log_step(thought="step")
        tl.finish(make_result())

        loaded = tl.get_by_id(tid)
        assert loaded is not None
        assert loaded["command"] == "open notepad"
        assert len(loaded["steps"]) == 1

        jsonl_files = list(base.glob("trajectories-*.jsonl"))
        assert len(jsonl_files) == 1
        lines = jsonl_files[0].read_text(encoding="utf-8").strip().splitlines()
        assert json.loads(lines[0])["id"] == tid

    def test_timestamps_are_timezone_aware(self, tmp_path):
        tl = TrajectoryLogger(base_dir=str(tmp_path / "traj"))
        tl.start("status")
        tl.log_step(thought="check")
        traj = tl.finish(make_result("status"))
        assert datetime.fromisoformat(traj.timestamp).tzinfo is not None
        assert datetime.fromisoformat(traj.steps[0].timestamp).tzinfo is not None

    def test_step_and_finish_without_active_trajectory(self, tmp_path):
        tl = TrajectoryLogger(base_dir=str(tmp_path / "traj"))
        tl.log_step(thought="orphan")  # must not raise
        assert tl.finish(make_result()) is None

    def test_get_recent_returns_newest_first(self, tmp_path):
        tl = TrajectoryLogger(base_dir=str(tmp_path / "traj"))
        ids = []
        for i in range(3):
            tid = tl.start(f"command {i}")
            tl.finish(make_result(f"command {i}"))
            ids.append(tid)
            time.sleep(0.02)  # ensure distinct mtimes

        recent = tl.get_recent(limit=2)
        assert len(recent) == 2
        assert recent[0]["id"] == ids[2]
        assert recent[1]["id"] == ids[1]

    def test_get_stats_counts_and_ignores_corrupt_files(self, tmp_path):
        base = tmp_path / "traj"
        tl = TrajectoryLogger(base_dir=str(base))
        now = datetime.now().astimezone().isoformat()
        write_trajectory_file(base, 1, "a", now, success=True,
                              steps=[{"step_number": 1}], duration_ms=100)
        write_trajectory_file(base, 2, "b", now, success=False,
                              steps=[{"step_number": 1}, {"step_number": 2}],
                              duration_ms=300)
        # Corrupt file matching the traj_*.json glob must not crash or skew stats
        (base / "traj_corrupt.json").write_text("{not json", encoding="utf-8")

        stats = tl.get_stats()
        assert stats["total"] == 3
        assert stats["sample_size"] == 2  # only parseable files counted
        assert stats["success_rate"] == 50.0
        assert stats["avg_steps"] == 1.5
        assert stats["avg_duration_ms"] == 200

    def test_get_stats_empty_dir(self, tmp_path):
        tl = TrajectoryLogger(base_dir=str(tmp_path / "traj"))
        stats = tl.get_stats()
        assert stats["total"] == 0
        assert stats["success_rate"] == 0


# ---------------------------------------------------------------------------
# SkillCurator
# ---------------------------------------------------------------------------

class TestSkillCurator:
    def test_detects_repeated_pattern(self, tmp_path):
        curator = make_curator(tmp_path, min_occurrences=3)
        base = curator.trajectory_logger.base_dir
        now = datetime.now(timezone.utc)

        similar = ["open notepad", "open notepad please", "jarvis open notepad"]
        for i, cmd in enumerate(similar):
            write_trajectory_file(base, i, cmd, (now - timedelta(hours=i)).isoformat())
        # One unrelated command should not form a pattern
        write_trajectory_file(base, 99, "check the weather in london", now.isoformat())

        patterns = curator.scan_for_patterns()
        assert len(patterns) == 1
        p = patterns[0]
        assert p.count == 3
        assert "notepad" in p.representative_command
        assert p.suggested_name
        assert len(p.suggested_triggers) >= 1
        assert p.avg_success_rate == 1.0
        assert p.confidence >= curator.similarity_threshold

    def test_handles_mixed_naive_and_aware_timestamps(self, tmp_path):
        """Recent trajectories must cluster even when timestamps mix naive
        local, aware-UTC, and 'Z'-suffixed formats (regression for the
        naive/aware comparison bug)."""
        curator = make_curator(tmp_path, min_occurrences=3)
        base = curator.trajectory_logger.base_dir
        stamps = [
            datetime.now().isoformat(),                                  # naive local
            datetime.now(timezone.utc).isoformat(),                      # aware UTC
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "Z",  # Z-suffixed
        ]
        for i, ts in enumerate(stamps):
            write_trajectory_file(base, i, "open notepad", ts)

        patterns = curator.scan_for_patterns()
        assert len(patterns) == 1
        assert patterns[0].count == 3
        # All three are recent: recency must not silently fall back to 0.5
        # (the old code raised TypeError on naive-vs-aware max()).
        assert patterns[0].confidence >= 0.8

    def test_excludes_trajectories_outside_lookback(self, tmp_path):
        curator = make_curator(tmp_path, min_occurrences=3, lookback_days=7)
        base = curator.trajectory_logger.base_dir
        old = datetime.now(timezone.utc) - timedelta(days=30)
        for i in range(3):
            write_trajectory_file(base, i, "open notepad", old.isoformat())
        assert curator.scan_for_patterns() == []

    def test_excludes_failed_trajectories(self, tmp_path):
        curator = make_curator(tmp_path, min_occurrences=3)
        base = curator.trajectory_logger.base_dir
        now = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            write_trajectory_file(base, i, "open notepad", now, success=False)
        assert curator.scan_for_patterns() == []

    def test_below_min_occurrences_not_reported(self, tmp_path):
        curator = make_curator(tmp_path, min_occurrences=3)
        base = curator.trajectory_logger.base_dir
        now = datetime.now(timezone.utc).isoformat()
        for i in range(2):
            write_trajectory_file(base, i, "open notepad", now)
        assert curator.scan_for_patterns() == []

    def test_save_get_dismiss_suggestions_roundtrip(self, tmp_path):
        curator = make_curator(tmp_path)
        pattern = CommandPattern(
            representative_command="open notepad",
            commands=["open notepad"] * 3,
            count=3,
            suggested_name="open_notepad",
            confidence=0.9,
        )
        curator.save_suggestions([pattern])
        assert curator.suggestions_file.exists()
        # No leftover temp file from the atomic write
        assert not list(curator.suggestions_file.parent.glob("*.tmp"))

        loaded = curator.get_suggestions()
        assert len(loaded) == 1
        assert loaded[0]["representative_command"] == "open notepad"
        assert loaded[0]["count"] == 3

        curator.dismiss_suggestion("open notepad")
        assert curator.get_suggestions() == []

    def test_normalize_strips_fillers(self, tmp_path):
        curator = make_curator(tmp_path)
        assert curator._normalize_command("Hey Jarvis please open   notepad") == "open notepad"

    def test_commands_similar_jaccard(self, tmp_path):
        curator = make_curator(tmp_path, similarity_threshold=0.7)
        assert curator._commands_similar("open notepad", "open notepad") is True
        assert curator._commands_similar("open notepad", "check weather london") is False
        assert curator._commands_similar("", "open notepad") is False


# ---------------------------------------------------------------------------
# SkillImprover
# ---------------------------------------------------------------------------

@pytest.fixture
def improver(tmp_path):
    manager = SkillManager(skills_dir=str(tmp_path / "skills"))
    logger = TrajectoryLogger(base_dir=str(tmp_path / "trajectories"))
    return SkillImprover(
        skill_manager=manager,
        trajectory_logger=logger,
        performance_file=str(tmp_path / "skills" / "performance.json"),
    )


class TestSkillImprover:
    def test_record_and_get_performance_roundtrip(self, improver):
        improver.track_execution("skill_x", True, duration_ms=100)
        improver.track_execution("skill_x", False, duration_ms=300, error="file not found")

        perf = improver.get_performance("skill_x")
        assert perf.skill_id == "skill_x"
        assert perf.total_runs == 2
        assert perf.successes == 1
        assert perf.failures == 1
        assert perf.success_rate == 0.5
        assert perf.avg_duration_ms == 200  # rolling average of 100 and 300
        assert perf.failure_reasons == {"file not found": 1}
        assert perf.last_run is not None
        assert perf.last_failure is not None

    def test_unknown_skill_returns_fresh_performance(self, improver):
        perf = improver.get_performance("does_not_exist")
        assert perf.total_runs == 0
        assert perf.success_rate == 0.0

    def test_get_all_performance(self, improver):
        improver.track_execution("skill_a", True, duration_ms=10)
        improver.track_execution("skill_b", False, duration_ms=20, error="timeout")

        all_perf = {p.skill_id: p for p in improver.get_all_performance()}
        assert set(all_perf) == {"skill_a", "skill_b"}
        assert all_perf["skill_a"].successes == 1
        assert all_perf["skill_b"].failures == 1

    def test_load_tolerates_unknown_keys(self, improver, tmp_path):
        """Extra keys from a newer file format must not silently reset stats."""
        perf_file = tmp_path / "skills" / "performance.json"
        perf_file.parent.mkdir(parents=True, exist_ok=True)
        perf_file.write_text(json.dumps({
            "updated_at": "2026-01-01T00:00:00+00:00",
            "performances": [
                {"skill_id": "s1", "total_runs": 5, "successes": 4,
                 "failures": 1, "success_rate": 0.8, "future_field": "x"},
            ],
        }), encoding="utf-8")

        perf = improver.get_performance("s1")
        assert perf.total_runs == 5
        assert perf.success_rate == 0.8

    def test_atomic_save_leaves_no_temp_file(self, improver, tmp_path):
        improver.track_execution("skill_x", True, duration_ms=5)
        skills_dir = tmp_path / "skills"
        assert (skills_dir / "performance.json").exists()
        assert not list(skills_dir.glob("*.tmp"))

    def test_persists_across_instances(self, improver, tmp_path):
        improver.track_execution("skill_x", True, duration_ms=50)
        reloaded = SkillImprover(
            skill_manager=improver.skill_manager,
            trajectory_logger=improver.trajectory_logger,
            performance_file=str(tmp_path / "skills" / "performance.json"),
        )
        assert reloaded.get_performance("skill_x").total_runs == 1


# ---------------------------------------------------------------------------
# AutonomousCreator
# ---------------------------------------------------------------------------

@pytest.fixture
def creator(tmp_path):
    manager = SkillManager(skills_dir=str(tmp_path / "skills"))
    return AutonomousCreator(skill_manager=manager)


def make_pattern(commands=None, name="open_notepad") -> CommandPattern:
    commands = commands if commands is not None else ["open notepad"] * 3
    return CommandPattern(
        representative_command=commands[0] if commands else "open notepad",
        commands=commands,
        count=len(commands),
        avg_success_rate=1.0,
        suggested_name=name,
        suggested_triggers=list(dict.fromkeys(commands)),
        confidence=0.9,
    )


class TestAutonomousCreator:
    def test_create_skill_from_pattern(self, creator):
        skill = creator.create_skill_from_pattern(make_pattern())
        assert skill is not None
        assert skill.name == "open_notepad"
        assert len(skill.steps) == 1  # duplicates deduplicated to one action
        assert skill.steps[0].action.type == ActionType.OPEN_APP
        assert skill.metadata.get("auto_generated") is True
        assert skill.status.value == "draft"  # not auto-approved
        # required trust derived from the planned action (open_app needs 2)
        assert skill.required_trust == 2

    def test_create_returns_none_for_unplannable_commands(self, creator):
        pattern = make_pattern(commands=["frobnicate the quux"] * 3, name="frob")
        assert creator.create_skill_from_pattern(pattern) is None

    def test_ensure_unique_name(self, creator):
        creator.skill_manager.create(name="open_notepad")
        assert creator._ensure_unique_name("open_notepad") == "open_notepad_2"
        assert creator._ensure_unique_name("brand_new") == "brand_new"

    def test_extract_common_actions_dedupes(self, creator):
        actions = creator._extract_common_actions(["open notepad", "open notepad"])
        assert len(actions) == 1
        assert actions[0].type == ActionType.OPEN_APP

    def test_calculate_required_trust(self, creator):
        low = Action(ActionType.STATUS, required_trust=1)
        high = Action(ActionType.RUN_TERMINAL, required_trust=3)
        assert creator._calculate_required_trust([low, high]) == 3
        assert creator._calculate_required_trust([]) == 1

    def test_generalize_with_llm_handles_empty_commands(self, creator):
        pattern = make_pattern(commands=[], name="empty")
        pattern.representative_command = "open notepad"
        result = creator.generalize_with_llm(pattern)  # must not raise IndexError
        assert result["name"] == "empty"
        assert "open notepad" in result["description"]

    def test_generate_description_mentions_examples(self, creator):
        pattern = make_pattern(commands=["open notepad", "open notepad please"])
        actions = creator._extract_common_actions(pattern.commands)
        desc = creator._generate_description(pattern, actions)
        assert "open notepad" in desc
        assert "open_app" in desc
