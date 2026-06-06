"""Skill recorder for turning successful commands into reusable macros."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from backend.skills.skill_manager import SkillManager
from backend.skills.skill_schema import Skill


@dataclass(slots=True)
class RecordingSession:
    name: str
    description: str = ""
    commands: List[str] = field(default_factory=list)
    active: bool = True


class SkillRecorder:
    def __init__(self, manager: SkillManager | None = None):
        self.manager = manager or SkillManager()
        self.session: RecordingSession | None = None

    def start(self, name: str, description: str = "") -> RecordingSession:
        if self.session and self.session.active:
            raise RuntimeError("A recording session is already active")
        self.session = RecordingSession(name=name, description=description)
        return self.session

    def record_command(self, command: str) -> None:
        if not self.session or not self.session.active:
            raise RuntimeError("No active recording session")
        self.session.commands.append(command)

    def stop(self, trigger_phrases: list[str] | None = None, tags: list[str] | None = None) -> Skill:
        if not self.session or not self.session.active:
            raise RuntimeError("No active recording session")
        self.session.active = False
        return self.manager.create_from_commands(
            self.session.name,
            self.session.commands,
            description=self.session.description,
            trigger_phrases=trigger_phrases or [self.session.name],
            tags=tags,
        )

    def cancel(self) -> None:
        if self.session:
            self.session.active = False
        self.session = None
