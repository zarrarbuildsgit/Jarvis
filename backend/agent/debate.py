"""Multi-agent debate layer for risky or ambiguous tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
import asyncio


@dataclass
class DebateConfig:
    enabled: bool = True
    rounds: int = 2
    personas: List[str] = field(default_factory=lambda: ["Planner", "Skeptic", "Security", "Optimizer"])


@dataclass
class DebateVerdict:
    summary: str
    recommended_plan: str
    objections: List[str]
    risk_level: int  # 1 low, 4 critical


class MultiAgentDebate:
    """Lightweight deterministic debate engine.

    This gives the product a real debate gate even when no external LLM is configured.
    It can later be swapped to call local LLM agents per persona.
    """

    def __init__(self, config: DebateConfig | None = None):
        self.config = config or DebateConfig()

    async def deliberate(self, command: str) -> DebateVerdict:
        await asyncio.sleep(0)
        cmd = command.lower()
        objections: list[str] = []
        risk = 1

        if any(k in cmd for k in ["delete", "remove", "format", "wipe"]):
            risk = max(risk, 3)
            objections.append("Destructive operation: require backup/confirmation and verify target path.")
        if any(k in cmd for k in ["install", "update", "driver", "registry", "service"]):
            risk = max(risk, 3)
            objections.append("System-changing operation: prefer signed installers, restore point, and admin confirmation.")
        if any(k in cmd for k in ["password", "token", "credential", "secret"]):
            risk = max(risk, 4)
            objections.append("Sensitive credential operation: do not expose secrets; require explicit user approval.")
        if any(k in cmd for k in ["send", "email", "message", "post"]):
            risk = max(risk, 2)
            objections.append("External communication: draft first and ask before sending.")

        if not objections:
            objections.append("No major objections; proceed with standard verify-after-action loop.")

        plan = "1) Clarify target if ambiguous. 2) Prefer reversible action. 3) Execute smallest safe step. 4) Verify screen/result. 5) Report uncertainty."
        return DebateVerdict(
            summary=f"{len(self.config.personas)} personas reviewed command; risk level {risk}/4.",
            recommended_plan=plan,
            objections=objections,
            risk_level=risk,
        )
