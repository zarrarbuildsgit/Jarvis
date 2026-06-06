"""Shared safety helpers for first-party plugins."""

from __future__ import annotations

from backend.agent.action_schema import Action
from backend.plugins.base import PluginResult
from backend.security.audit_log import AuditLogger
from backend.security.policy import PolicyEngine


class SafePluginMixin:
    """Run a policy check before a plugin executes a concrete action."""

    def __init__(self):
        self.policy = PolicyEngine()
        self.audit = AuditLogger()

    def check_action(self, action: Action, command: str, context: dict) -> PluginResult | None:
        trust_level = int(context.get("trust_level", 1))
        decision = self.policy.evaluate(action, trust_level=trust_level, context=context)
        self.audit.record_policy(decision, action, command)
        if decision.blocked:
            msg = f"🛑 Blocked by safety policy: {decision.reason}"
            self.audit.record("plugin_action_blocked", msg, {"command": command, "action": action.to_dict(), "decision": decision.to_dict()})
            return PluginResult(True, False, msg, getattr(self, "name", None), {"decision": decision.to_dict()})
        if decision.needs_approval:
            # Plugins do not execute approval-resume yet; they fail closed and surface the reason.
            msg = f"⚠️ Approval required before plugin action: {decision.reason}"
            self.audit.record("plugin_approval_required", msg, {"command": command, "action": action.to_dict(), "decision": decision.to_dict()})
            return PluginResult(True, False, msg, getattr(self, "name", None), {"decision": decision.to_dict()})
        return None
