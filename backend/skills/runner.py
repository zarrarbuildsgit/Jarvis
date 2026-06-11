"""Skill runner that executes skill steps through the Sprint 1/2 action runtime."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from backend.agent.action_schema import RuntimeResult
from backend.skills.skill_manager import SkillManager
from backend.skills.skill_schema import Skill


class SkillRunner:
    def __init__(self, runtime, manager: SkillManager | None = None):
        self.runtime = runtime
        self.manager = manager or SkillManager()
        self._improver = None  # Lazy load to avoid circular imports

    @property
    def improver(self):
        if self._improver is None:
            from backend.skills.improver import SkillImprover
            self._improver = SkillImprover(skill_manager=self.manager)
        return self._improver

    async def run(self, skill_id_or_name: str, context: Optional[Dict[str, Any]] = None) -> RuntimeResult:
        skill = self.manager.get(skill_id_or_name)
        if not skill:
            return RuntimeResult(skill_id_or_name, False, False, f"Skill not found: {skill_id_or_name}")
        return await self.run_skill(skill, context)

    async def run_skill(self, skill: Skill, context: Optional[Dict[str, Any]] = None) -> RuntimeResult:
        context = context or {}
        actions = [step.action for step in skill.steps]
        if not actions:
            return RuntimeResult(skill.name, True, False, f"Skill has no steps: {skill.name}")
        if self.runtime.executor is None:
            return RuntimeResult(skill.name, True, False, "Action runtime has no executor configured")

        import time
        start_time = time.time()
        
        trust_level = int(context.get("trust_level", getattr(self.runtime, "trust_level_getter", lambda: 1)()))
        results = []
        policy_decisions = []
        required_step_failed = False

        for step in skill.steps:
            action = step.action
            decision = self.runtime.policy_engine.evaluate(action, trust_level=trust_level, context={**context, "skill_id": skill.id})
            policy_decisions.append(decision)
            self.runtime.audit_logger.record_policy(decision, action, skill.name)

            if decision.blocked:
                message = f"🛑 Skill blocked by safety policy: {decision.reason}"
                self.runtime.audit_logger.record("skill_action_blocked", message, {"skill": skill.to_dict(), "action": action.to_dict(), "decision": decision.to_dict()})
                result = RuntimeResult(skill.name, True, False, message, results=results, metadata={"skill": skill.to_dict(), "policy_decisions": [d.to_dict() for d in policy_decisions], **context})
                # Track failure
                self.improver.track_execution(skill.id, False, int((time.time() - start_time) * 1000), message)
                return result

            if decision.needs_approval:
                approval = self.runtime.approval_manager.create(action, decision, command=f"skill:{skill.name}")
                message = f"⚠️ Skill approval required ({approval.id}): {decision.reason}"
                self.runtime.audit_logger.record("skill_approval_requested", message, {"skill": skill.to_dict(), "approval": approval.to_dict()})
                result = RuntimeResult(skill.name, True, False, message, results=results, metadata={"skill": skill.to_dict(), "approval_id": approval.id, "policy_decisions": [d.to_dict() for d in policy_decisions], **context})
                # Track as not run (needs approval)
                return result

            result = await self.runtime.executor.execute(action)
            results.append(result)
            self.runtime.audit_logger.record_action_result(result, action, f"skill:{skill.name}")
            if step.delay_after_seconds > 0:
                await asyncio.sleep(step.delay_after_seconds)
            if not result.success and not step.optional:
                required_step_failed = True
                break

        # Optional-step failures are tolerated: the skill fails only if a
        # required step failed (early break) or not every step was attempted.
        success = bool(results) and not required_step_failed and len(results) == len(actions)
        skill.touch_run()
        self.manager.save(skill)
        message = f"✅ Skill completed: {skill.name}" if success else f"❌ Skill stopped: {skill.name}"
        final_result = RuntimeResult(skill.name, True, success, message, results=results, metadata={"skill": skill.to_dict(), "policy_decisions": [d.to_dict() for d in policy_decisions], **context})
        
        # Track performance
        duration_ms = int((time.time() - start_time) * 1000)
        if success:
            error_msg = None
        else:
            failed = next((r for r in results if not r.success), None)
            error_msg = (failed.error or failed.message or "Unknown error") if failed else "Unknown error"
        self.improver.track_execution(skill.id, success, duration_ms, error_msg)
        
        return final_result
