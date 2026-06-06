"""Sprint 11 smoke checks.

Run with:
    uv run python scripts/smoke_sprint11.py

Validates skill creation from commands, trigger matching, persistence, recording,
runner safety policy handling, and API source wiring without launching desktop apps.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.action_schema import ActionResult, ActionStatus
from backend.security.approval import ApprovalManager
from backend.security.audit_log import AuditLogger
from backend.security.policy import PolicyEngine
from backend.skills import SkillManager, SkillRecorder, SkillRunner


class DummyExecutor:
    async def execute(self, action):
        return ActionResult(action.id, action.type, ActionStatus.SUCCESS).finish(ActionStatus.SUCCESS, f"executed {action.type.value}")


class DummyRuntime:
    def __init__(self, root: Path):
        self.executor = DummyExecutor()
        self.policy_engine = PolicyEngine()
        self.approval_manager = ApprovalManager(str(root / "approvals.json"))
        self.audit_logger = AuditLogger(str(root / "audit.jsonl"))
        self.trust_level_getter = lambda: 4


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


async def async_checks(root: Path, manager: SkillManager) -> None:
    runtime = DummyRuntime(root)
    runner = SkillRunner(runtime, manager)
    skill = manager.find_match("start coding mode")
    result = await runner.run_skill(skill, {"trust_level": 4})
    assert_true(result.success, "safe skill runs")
    assert_true(manager.get(skill.id).run_count == 1, "run count increments")

    dangerous = manager.create_from_commands("danger mode", ["run command rm -rf /"], trigger_phrases=["danger mode"])
    danger_result = await runner.run_skill(dangerous, {"trust_level": 4})
    assert_true(not danger_result.success and "blocked" in danger_result.message.lower(), "dangerous skill blocked")


def main() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = SkillManager(str(root / "skills"))
        skill = manager.create_from_commands(
            "coding mode",
            ["open notepad", "set clipboard to hello"],
            description="Open editor and prepare clipboard",
            trigger_phrases=["start coding mode", "coding mode"],
            tags=["dev"],
        )
        assert_true(skill.steps and skill.required_trust >= 2, "skill created from deterministic commands")
        assert_true(manager.find_match("start coding mode").id == skill.id, "trigger phrase match")

        reloaded = SkillManager(str(root / "skills"))
        assert_true(reloaded.get(skill.id) is not None, "skill persisted")

        recorder = SkillRecorder(manager)
        recorder.start("morning setup")
        recorder.record_command("open notepad")
        recorded = recorder.stop(trigger_phrases=["morning setup"])
        assert_true(recorded.steps, "recorder creates skill")

        asyncio.run(async_checks(root, manager))

    api = Path("backend/api.py").read_text(encoding="utf-8")
    for endpoint in ["/api/skills", "/api/skills/{skill_id}/run"]:
        assert_true(endpoint in api, f"api endpoint wired: {endpoint}")

    print("✅ Sprint 11 smoke checks passed")


if __name__ == "__main__":
    main()
