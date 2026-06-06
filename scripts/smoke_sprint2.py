"""Sprint 2 smoke checks.

Run with:
    uv run python scripts/smoke_sprint2.py

This avoids heavyweight JARVIS runtime imports and validates the safety policy,
approval store, and audit logger contracts.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.action_schema import Action, ActionType
from backend.security.approval import ApprovalManager
from backend.security.audit_log import AuditLogger
from backend.security.policy import PolicyDecisionType, PolicyEngine


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> None:
    engine = PolicyEngine()

    read = Action(ActionType.READ_FILE, {"filepath": "README.md"}, required_trust=1)
    assert_equal(engine.evaluate(read, trust_level=1).decision, PolicyDecisionType.ALLOW, "read action")

    write = Action(ActionType.WRITE_FILE, {"filepath": "notes.txt", "content": "hello"}, required_trust=2)
    write_decision = engine.evaluate(write, trust_level=1)
    assert_equal(write_decision.decision, PolicyDecisionType.REQUIRE_APPROVAL, "low trust write")

    dangerous = Action(ActionType.RUN_TERMINAL, {"command": "rm -rf /"}, required_trust=2)
    assert_equal(engine.evaluate(dangerous, trust_level=4).decision, PolicyDecisionType.BLOCK, "blocked terminal")

    install = Action(ActionType.RUN_TERMINAL, {"command": "pip install requests"}, required_trust=2)
    assert_equal(engine.evaluate(install, trust_level=3).decision, PolicyDecisionType.REQUIRE_APPROVAL, "install approval")

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        approvals = ApprovalManager(str(root / "approvals.json"))
        request = approvals.create(write, write_decision, command="create file notes.txt with hello")
        assert_equal(len(approvals.list("pending")), 1, "pending approval count")
        approvals.approve(request.id, resolved_by="smoke")
        assert_equal(approvals.is_approved(request.id), True, "approval resolution")

        audit = AuditLogger(str(root / "audit.jsonl"))
        audit.record("smoke", "audit works", {"ok": True})
        assert_equal(audit.tail(1)[0]["message"], "audit works", "audit tail")

    print("✅ Sprint 2 smoke checks passed")


if __name__ == "__main__":
    main()
