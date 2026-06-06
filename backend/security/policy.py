"""Action-level safety policy for JARVIS.

Sprint 2 purpose:
- evaluate every structured action before execution
- block obviously dangerous operations
- require approval for sensitive or trust-elevated actions
- keep decisions deterministic and auditable
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import re

try:  # PyYAML is in project deps, but policy must still import in minimal test envs.
    import yaml
except Exception:  # pragma: no cover - dependency fallback
    yaml = None

from backend.agent.action_schema import Action, ActionType


class PolicyDecisionType(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


@dataclass(slots=True)
class PolicyDecision:
    action_id: str
    action_type: ActionType
    decision: PolicyDecisionType
    reason: str
    risk_level: int = 1  # 1 low, 4 critical
    required_trust: int = 1
    matched_rules: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def allowed(self) -> bool:
        return self.decision == PolicyDecisionType.ALLOW

    @property
    def needs_approval(self) -> bool:
        return self.decision == PolicyDecisionType.REQUIRE_APPROVAL

    @property
    def blocked(self) -> bool:
        return self.decision == PolicyDecisionType.BLOCK

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["action_type"] = self.action_type.value
        data["decision"] = self.decision.value
        return data


class PolicyEngine:
    """Deterministic action policy engine.

    The policy starts with safe built-in defaults, then optionally loads extra
    regex patterns from `backend/security/rules.yaml`.
    """

    READ_ONLY_ACTIONS = {
        ActionType.NOOP,
        ActionType.RESPOND,
        ActionType.STATUS,
        ActionType.LIST_PLUGINS,
        ActionType.LIST_WINDOWS,
        ActionType.LIST_PROCESSES,
        ActionType.GET_CLIPBOARD,
        ActionType.LIST_FILES,
        ActionType.READ_FILE,
        ActionType.ANALYZE_SCREEN,
    }

    INTERACTIVE_ACTIONS = {
        ActionType.OPEN_APP,
        ActionType.FOCUS_WINDOW,
        ActionType.SET_CLIPBOARD,
        ActionType.PASTE_CLIPBOARD,
        ActionType.CLICK,
        ActionType.TYPE_TEXT,
        ActionType.PRESS_KEY,
    }

    WRITE_ACTIONS = {
        ActionType.WRITE_FILE,
        ActionType.RUN_TERMINAL,
    }

    DEFAULT_BLOCK_PATTERNS = [
        r"\brm\s+-rf\s+[/\\]",
        r"\bdel\s+/f\s+/s\s+/q\b",
        r"\bformat\b",
        r"\bdiskpart\b",
        r"\bbcdedit\b",
        r"\breg\s+delete\b",
        r"\btakeown\b.*\b[/\\]",
        r"\bcipher\s+/w\b",
        r"\bshutdown\b",
        r"\brestart-computer\b",
        r"\bstop-computer\b",
        r"\bnet\s+user\b.*\b/add\b",
        r"\bnet\s+localgroup\s+administrators\b",
    ]

    DEFAULT_APPROVAL_PATTERNS = [
        r"\binstall\b",
        r"\buninstall\b",
        r"\bwinget\b",
        r"\bchoco\b",
        r"\bscoop\b",
        r"\bpip\s+install\b",
        r"\bnpm\s+install\b",
        r"\bdelete\b",
        r"\bremove\b",
        r"\brmdir\b",
        r"\berase\b",
        r"\btaskkill\b",
        r"\bsc\s+(create|delete|config)\b",
        r"\bnew-service\b",
        r"\bset-executionpolicy\b",
    ]

    SENSITIVE_TERMS = ["password", "token", "secret", "credential", "private key", "api key"]

    def __init__(self, rules_file: str = "backend/security/rules.yaml"):
        self.rules_file = Path(rules_file)
        self.block_patterns = list(self.DEFAULT_BLOCK_PATTERNS)
        self.approval_patterns = list(self.DEFAULT_APPROVAL_PATTERNS)
        self.sensitive_terms = list(self.SENSITIVE_TERMS)
        self.load_rules()

    def load_rules(self) -> None:
        if not self.rules_file.exists() or yaml is None:
            return
        try:
            data = yaml.safe_load(self.rules_file.read_text(encoding="utf-8")) or {}
            self.block_patterns.extend(data.get("blocked_command_patterns", []) or [])
            self.approval_patterns.extend(data.get("approval_command_patterns", []) or [])
            self.sensitive_terms.extend(data.get("sensitive_terms", []) or [])
        except Exception:
            # Policy must fail closed-ish through defaults, not crash app startup.
            return

    def evaluate(self, action: Action, trust_level: int = 1, context: Optional[Dict[str, Any]] = None) -> PolicyDecision:
        context = context or {}
        matched: list[str] = []
        required_trust = max(action.required_trust, self._required_trust_for_action(action))

        # Trust elevation check first, except read-only actions are always okay at level 1.
        if required_trust > trust_level:
            return PolicyDecision(
                action.id,
                action.type,
                PolicyDecisionType.REQUIRE_APPROVAL,
                f"Action requires trust level {required_trust}; current level is {trust_level}.",
                risk_level=max(2, required_trust),
                required_trust=required_trust,
                matched_rules=["trust_level"],
            )

        sensitive_hit = self._contains_sensitive_material(action)
        if sensitive_hit:
            return PolicyDecision(
                action.id,
                action.type,
                PolicyDecisionType.REQUIRE_APPROVAL,
                f"Action references sensitive term: {sensitive_hit}.",
                risk_level=4,
                required_trust=max(required_trust, 3),
                matched_rules=["sensitive_material"],
            )

        if action.type == ActionType.RUN_TERMINAL:
            command = str(action.parameters.get("command", ""))
            block_match = self._first_match(command, self.block_patterns)
            if block_match:
                return PolicyDecision(
                    action.id,
                    action.type,
                    PolicyDecisionType.BLOCK,
                    f"Terminal command matches blocked pattern: {block_match}",
                    risk_level=4,
                    required_trust=4,
                    matched_rules=[block_match],
                    metadata={"command": command},
                )
            approval_match = self._first_match(command, self.approval_patterns)
            if approval_match:
                return PolicyDecision(
                    action.id,
                    action.type,
                    PolicyDecisionType.REQUIRE_APPROVAL,
                    f"Terminal command requires approval: {approval_match}",
                    risk_level=3,
                    required_trust=max(required_trust, 3),
                    matched_rules=[approval_match],
                    metadata={"command": command},
                )

        if action.type == ActionType.WRITE_FILE and self._is_sensitive_path(str(action.parameters.get("filepath", ""))):
            return PolicyDecision(
                action.id,
                action.type,
                PolicyDecisionType.REQUIRE_APPROVAL,
                "Writing to a sensitive/system path requires approval.",
                risk_level=3,
                required_trust=max(required_trust, 3),
                matched_rules=["sensitive_path"],
            )

        if action.type in self.READ_ONLY_ACTIONS:
            return PolicyDecision(action.id, action.type, PolicyDecisionType.ALLOW, "Read-only action allowed.", 1, required_trust)
        if action.type in self.INTERACTIVE_ACTIONS:
            return PolicyDecision(action.id, action.type, PolicyDecisionType.ALLOW, "Interactive action allowed by trust level.", 2, required_trust)
        if action.type in self.WRITE_ACTIONS:
            return PolicyDecision(action.id, action.type, PolicyDecisionType.ALLOW, "Write/terminal action allowed by trust level.", 2, required_trust)

        return PolicyDecision(
            action.id,
            action.type,
            PolicyDecisionType.REQUIRE_APPROVAL,
            "Unknown action type requires approval by default.",
            risk_level=3,
            required_trust=max(required_trust, 3),
            matched_rules=["unknown_action"],
        )

    def evaluate_plan(self, actions: Iterable[Action], trust_level: int = 1, context: Optional[Dict[str, Any]] = None) -> List[PolicyDecision]:
        return [self.evaluate(action, trust_level, context) for action in actions]

    def _required_trust_for_action(self, action: Action) -> int:
        if action.type in self.READ_ONLY_ACTIONS:
            return 1
        if action.type in self.INTERACTIVE_ACTIONS:
            return 2
        if action.type == ActionType.WRITE_FILE:
            return 2
        if action.type == ActionType.RUN_TERMINAL:
            return 2
        return action.required_trust

    def _contains_sensitive_material(self, action: Action) -> str | None:
        haystack = " ".join([action.description, str(action.parameters), str(action.metadata)]).lower()
        for term in self.sensitive_terms:
            if term.lower() in haystack:
                return term
        return None

    def _first_match(self, text: str, patterns: Iterable[str]) -> str | None:
        for pattern in patterns:
            try:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    return pattern
            except re.error:
                continue
        return None

    def _is_sensitive_path(self, filepath: str) -> bool:
        path = filepath.lower().replace("/", "\\")
        sensitive_roots = [
            "c:\\windows",
            "c:\\program files",
            "c:\\program files (x86)",
            "c:\\programdata",
            "\\windows\\system32",
        ]
        return any(path.startswith(root) or root in path for root in sensitive_roots)
