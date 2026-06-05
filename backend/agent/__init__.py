"""JARVIS Agent Core.

Heavy agent orchestration imports are lazy so lightweight modules such as the
planner/action schema can be imported without loading CrewAI/loguru dependencies.
"""

from __future__ import annotations

from typing import Any

__all__ = ["JARVIS_Crew"]


def __getattr__(name: str) -> Any:
    if name == "JARVIS_Crew":
        from backend.agent.crew import JARVIS_Crew

        return JARVIS_Crew
    raise AttributeError(name)
