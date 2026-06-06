"""Skill storage and lookup."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import json
import re

from backend.agent.planner import DeterministicPlanner
from backend.skills.skill_schema import Skill, SkillStatus, SkillStep, now_iso


class SkillManager:
    def __init__(self, skills_dir: str = "data/skills"):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.planner = DeterministicPlanner()
        self._skills: Dict[str, Skill] = {}
        self.load()

    def load(self) -> None:
        self._skills = {}
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        for path in self.skills_dir.glob("*.json"):
            try:
                skill = Skill.from_dict(json.loads(path.read_text(encoding="utf-8")))
                self._skills[skill.id] = skill
            except Exception:
                continue

    def list(self, status: str | SkillStatus | None = None) -> List[Skill]:
        skills = list(self._skills.values())
        if status is not None:
            status_enum = SkillStatus(status)
            skills = [skill for skill in skills if skill.status == status_enum]
        return sorted(skills, key=lambda s: s.name.lower())

    def get(self, skill_id_or_name: str) -> Optional[Skill]:
        if skill_id_or_name in self._skills:
            return self._skills[skill_id_or_name]
        needle = skill_id_or_name.lower().strip()
        return next((s for s in self._skills.values() if s.name.lower() == needle), None)

    def find_match(self, command: str) -> Optional[Skill]:
        return next((skill for skill in self.list(SkillStatus.ENABLED) if skill.matches(command)), None)

    def create(self, name: str, description: str = "", trigger_phrases: Optional[List[str]] = None, steps: Optional[List[SkillStep]] = None, tags: Optional[List[str]] = None, required_trust: int = 1) -> Skill:
        skill = Skill(
            name=name.strip(),
            description=description.strip(),
            trigger_phrases=trigger_phrases or [name.strip()],
            steps=steps or [],
            tags=tags or [],
            required_trust=required_trust,
        )
        self._skills[skill.id] = skill
        self.save(skill)
        return skill

    def create_from_commands(self, name: str, commands: List[str], description: str = "", trigger_phrases: Optional[List[str]] = None, tags: Optional[List[str]] = None) -> Skill:
        steps: list[SkillStep] = []
        required_trust = 1
        for idx, command in enumerate(commands, start=1):
            plan = self.planner.plan(command)
            if plan.is_empty:
                continue
            for action in plan.actions:
                required_trust = max(required_trust, action.required_trust)
                steps.append(SkillStep(action=action, name=f"Step {idx}: {command}", notes="Recorded from command"))
        if not steps:
            raise ValueError("No deterministic actions could be planned from the provided commands")
        return self.create(name, description, trigger_phrases or [name], steps, tags, required_trust)

    def update(self, skill_id: str, **changes) -> Skill:
        skill = self._require(skill_id)
        for key in ["name", "description", "trigger_phrases", "tags", "metadata", "required_trust"]:
            if key in changes:
                setattr(skill, key, changes[key])
        if "status" in changes:
            skill.status = SkillStatus(changes["status"])
        if "steps" in changes:
            skill.steps = [step if isinstance(step, SkillStep) else SkillStep.from_dict(step) for step in changes["steps"]]
        skill.updated_at = now_iso()
        self.save(skill)
        return skill

    def delete(self, skill_id: str) -> bool:
        skill = self._skills.pop(skill_id, None)
        if not skill:
            return False
        path = self.path_for(skill)
        if path.exists():
            path.unlink()
        return True

    def save(self, skill: Skill) -> None:
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.path_for(skill).write_text(json.dumps(skill.to_dict(), indent=2), encoding="utf-8")

    def path_for(self, skill: Skill) -> Path:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", skill.name.lower()).strip("_") or skill.id
        return self.skills_dir / f"{slug}_{skill.id}.json"

    def _require(self, skill_id: str) -> Skill:
        skill = self.get(skill_id)
        if not skill:
            raise KeyError(f"Skill not found: {skill_id}")
        return skill
