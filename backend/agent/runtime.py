"""JARVIS deterministic action runtime.

The runtime is the single bridge between user commands and executable actions.
Future systems (voice, dashboard, skills, scheduler) should call this instead of
calling low-level tools directly.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from backend.agent.action_schema import ActionPlan, RuntimeResult
from backend.agent.executor import ActionExecutor
from backend.agent.observation import ObservationBuilder
from backend.agent.planner import DeterministicPlanner
from backend.agent.trajectory import TrajectoryLogger
from backend.security.approval import ApprovalManager
from backend.security.audit_log import AuditLogger
from backend.security.policy import PolicyDecisionType, PolicyEngine


class ActionRuntime:
    """Plan, policy-check, and execute deterministic actions."""

    def __init__(
        self,
        *,
        planner: Optional[DeterministicPlanner] = None,
        executor: Optional[ActionExecutor] = None,
        observation_builder: Optional[ObservationBuilder] = None,
        policy_engine: Optional[PolicyEngine] = None,
        approval_manager: Optional[ApprovalManager] = None,
        audit_logger: Optional[AuditLogger] = None,
        trajectory_logger: Optional[TrajectoryLogger] = None,
        trust_level_getter=None,
        min_confidence: float = 0.75,
    ):
        self.planner = planner or DeterministicPlanner()
        self.executor = executor
        self.observation_builder = observation_builder
        self.policy_engine = policy_engine or PolicyEngine()
        self.approval_manager = approval_manager or ApprovalManager()
        self.audit_logger = audit_logger or AuditLogger()
        self.trajectory_logger = trajectory_logger or TrajectoryLogger()
        self.trust_level_getter = trust_level_getter or (lambda: 1)
        self.min_confidence = min_confidence

    def plan(self, command: str) -> ActionPlan:
        return self.planner.plan(command)

    async def run(self, command: str, context: Optional[Dict[str, Any]] = None) -> RuntimeResult:
        context = context or {}
        plan = self.plan(command)
        
        # Start trajectory logging
        trajectory_id = self.trajectory_logger.start(
            command=command,
            plan=plan,
            metadata={"context": context, "trust_level": context.get("trust_level")}
        )
        
        try:
            if plan.is_empty or plan.confidence < self.min_confidence:
                result = RuntimeResult(
                    command=command,
                    handled=False,
                    success=False,
                    message="No deterministic action plan matched this command.",
                    plan=plan,
                    metadata={"confidence": plan.confidence, **context},
                )
                self.trajectory_logger.log_step(
                    thought=f"No plan found (confidence {plan.confidence} < {self.min_confidence})",
                    action=None,
                    result=None
                )
                self.trajectory_logger.finish(result)
                return result

            if self.executor is None:
                result = RuntimeResult(
                    command=command,
                    handled=True,
                    success=False,
                    message="Action runtime has no executor configured.",
                    plan=plan,
                    metadata=context,
                )
                self.trajectory_logger.log_step(
                    thought="Executor not configured",
                    action=None,
                    result=None
                )
                self.trajectory_logger.finish(result)
                return result

            logger.info(f"Runtime executing plan {plan.id} with {len(plan.actions)} action(s): {plan.summary}")

            trust_level = int(context.get("trust_level", self.trust_level_getter()))
            approved_action_ids = set(context.get("approved_action_ids", []) or [])
            policy_decisions = []
            results = []

            for action in plan.actions:
                decision = self.policy_engine.evaluate(action, trust_level=trust_level, context=context)
                policy_decisions.append(decision)
                self.audit_logger.record_policy(decision, action, command)

                if decision.blocked:
                    message = f"🛑 Blocked by safety policy: {decision.reason}"
                    self.audit_logger.record("action_blocked", message, {"command": command, "action": action.to_dict(), "decision": decision.to_dict()})
                    self.trajectory_logger.log_step(
                        thought=f"Action blocked by policy: {decision.reason}",
                        action=action.to_dict(),
                        observation={"decision": decision.to_dict()}
                    )
                    result = RuntimeResult(
                        command=command,
                        handled=True,
                        success=False,
                        message=message,
                        plan=plan,
                        results=results,
                        metadata={**context, "policy_decisions": [d.to_dict() for d in policy_decisions]},
                    )
                    self.trajectory_logger.finish(result)
                    return result

                if decision.needs_approval and action.id not in approved_action_ids:
                    approval = self.approval_manager.create(action, decision, command=command)
                    message = f"⚠️ Approval required ({approval.id}): {decision.reason}"
                    self.audit_logger.record(
                        "approval_requested",
                        message,
                        {"command": command, "approval": approval.to_dict(), "action": action.to_dict(), "decision": decision.to_dict()},
                    )
                    self.trajectory_logger.log_step(
                        thought=f"Action requires approval: {decision.reason}",
                        action=action.to_dict(),
                        observation={"approval_id": approval.id, "decision": decision.to_dict()}
                    )
                    result = RuntimeResult(
                        command=command,
                        handled=True,
                        success=False,
                        message=message,
                        plan=plan,
                        results=results,
                        metadata={
                            **context,
                            "approval_id": approval.id,
                            "policy_decisions": [d.to_dict() for d in policy_decisions],
                        },
                    )
                    self.trajectory_logger.finish(result)
                    return result

                # Log action execution
                self.trajectory_logger.log_step(
                    thought=f"Executing action: {action.description or action.type.value}",
                    action=action.to_dict()
                )
                
                result = await self.executor.execute(action)
                results.append(result)
                self.audit_logger.record_action_result(result, action, command)
                
                # Log result
                self.trajectory_logger.log_step(
                    thought=f"Action completed: {'success' if result.success else 'failed'}",
                    action=action.to_dict(),
                    observation={"output": str(result.output)[:200] if result.output else None},
                    result=result
                )
                
                if not result.success:
                    break

            success = bool(results) and all(r.success for r in results)
            message = self._summarize(plan, results, success)
            final_result = RuntimeResult(
                command=command,
                handled=True,
                success=success,
                message=message,
                plan=plan,
                results=results,
                metadata={**context, "policy_decisions": [d.to_dict() for d in policy_decisions]},
            )
            
            # Finish trajectory logging
            self.trajectory_logger.finish(final_result)
            
            return final_result
            
        except Exception as e:
            logger.exception(f"Runtime execution failed for command '{command}': {e}")
            # Ensure trajectory is finished even on exception
            try:
                error_result = RuntimeResult(
                    command=command,
                    handled=False,
                    success=False,
                    message=f"Runtime error: {str(e)}",
                    plan=plan,
                    metadata=context,
                )
                self.trajectory_logger.log_step(
                    thought=f"Exception occurred: {str(e)}",
                    action=None,
                    observation={"error": str(e)}
                )
                self.trajectory_logger.finish(error_result)
            except Exception as log_exc:
                logger.warning(f"Failed to finalize trajectory after runtime error: {log_exc}")
            raise

    def _summarize(self, plan: ActionPlan, results, success: bool) -> str:
        if not results:
            return f"No actions executed for: {plan.summary}"
        if len(results) == 1:
            result = results[0]
            prefix = "✅" if result.success else "❌"
            return f"{prefix} {result.message or result.error or plan.summary}"
        completed = sum(1 for r in results if r.success)
        if success:
            return f"✅ Completed {completed}/{len(results)} actions: {plan.summary}"
        failed = next((r for r in results if not r.success), results[-1])
        return f"❌ Completed {completed}/{len(results)} actions before failure: {failed.message or failed.error}"
