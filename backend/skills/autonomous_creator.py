"""
JARVIS Autonomous Skill Creator
Sprint 2: Uses local LLM to generalize command patterns into reusable skills
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.agent.planner import DeterministicPlanner
from backend.skills.curator import CommandPattern
from backend.skills.skill_manager import SkillManager
from backend.skills.skill_schema import Skill


class AutonomousCreator:
    """Creates skills automatically from command patterns using local LLM"""
    
    def __init__(
        self,
        skill_manager: Optional[SkillManager] = None,
        planner: Optional[DeterministicPlanner] = None,
    ):
        self.skill_manager = skill_manager or SkillManager()
        self.planner = planner or DeterministicPlanner()
    
    def create_skill_from_pattern(
        self,
        pattern: CommandPattern,
        use_llm: bool = True,
        auto_approve: bool = False,
    ) -> Optional[Skill]:
        """
        Create a skill from a detected pattern
        
        Args:
            pattern: Detected command pattern
            use_llm: Whether to use LLM for generalization (future)
            auto_approve: Whether to enable skill immediately
        
        Returns:
            Created skill or None if failed
        """
        try:
            logger.info(f"Creating skill from pattern: {pattern.representative_command} (count={pattern.count})")
            
            # Step 1: Analyze commands to find common actions
            actions = self._extract_common_actions(pattern.commands)
            
            if not actions:
                logger.warning(f"No actions extracted from pattern: {pattern.commands}")
                return None
            
            # Step 2: Generate skill metadata
            name = pattern.suggested_name or "auto_skill"
            description = self._generate_description(pattern, actions)
            triggers = pattern.suggested_triggers
            
            # Step 3: Ensure unique name
            name = self._ensure_unique_name(name)
            
            # Step 4: Create skill
            skill = self.skill_manager.create(
                name=name,
                description=description,
                trigger_phrases=triggers,
                steps=[],  # We'll add steps via update
                tags=["auto-generated", "pattern-based"],
                required_trust=self._calculate_required_trust(actions),
            )
            
            # Step 5: Add steps
            from backend.skills.skill_schema import SkillStep
            steps = []
            for idx, action in enumerate(actions, 1):
                step = SkillStep(
                    action=action,
                    name=f"Step {idx}",
                    notes=f"Auto-generated from pattern (seen {pattern.count} times)"
                )
                steps.append(step)
            
            # Update skill with steps
            skill = self.skill_manager.update(
                skill.id,
                steps=[s.to_dict() for s in steps],
                metadata={
                    "auto_generated": True,
                    "pattern": pattern.to_dict(),
                    "created_from": "curator",
                    "source_commands": pattern.commands[:5],  # Store sample
                }
            )
            
            # Step 6: Set status
            if not auto_approve:
                # Create as draft for user review
                from backend.skills.skill_schema import SkillStatus
                skill = self.skill_manager.update(skill.id, status=SkillStatus.DRAFT.value)
            
            logger.info(f"Created skill '{skill.name}' (id={skill.id}) from pattern")
            return skill
            
        except Exception as e:
            logger.error(f"Failed to create skill from pattern: {e}")
            return None
    
    def _extract_common_actions(self, commands: List[str]) -> List:
        """Extract common actions from similar commands"""
        actions = []
        seen_actions = set()
        
        for command in commands:
            try:
                plan = self.planner.plan(command)
                if plan.is_empty:
                    continue
                
                for action in plan.actions:
                    # Create a signature to deduplicate
                    sig = f"{action.type.value}:{json.dumps(action.parameters, sort_keys=True)}"
                    if sig not in seen_actions:
                        seen_actions.add(sig)
                        actions.append(action)
                        
                        # Limit to reasonable number
                        if len(actions) >= 5:
                            break
            except Exception as e:
                logger.warning(f"Failed to plan command '{command}': {e}")
                continue
            
            if len(actions) >= 5:
                break
        
        return actions
    
    def _generate_description(self, pattern: CommandPattern, actions: List) -> str:
        """Generate skill description"""
        parts = []
        
        parts.append(f"Auto-generated skill from {pattern.count} similar commands.")
        parts.append(f"Success rate: {pattern.avg_success_rate:.0%}")
        
        if actions:
            action_types = [a.type.value for a in actions]
            parts.append(f"Actions: {', '.join(action_types)}")
        
        # Add example commands
        if pattern.commands:
            examples = pattern.commands[:2]
            parts.append(f"Examples: '{examples[0]}'")
            if len(examples) > 1:
                parts[-1] += f", '{examples[1]}'"
        
        return " ".join(parts)
    
    def _ensure_unique_name(self, base_name: str) -> str:
        """Ensure skill name is unique"""
        name = base_name
        counter = 1
        
        while self.skill_manager.get(name):
            counter += 1
            name = f"{base_name}_{counter}"
            if counter > 100:  # Safety limit
                import uuid
                name = f"{base_name}_{uuid.uuid4().hex[:6]}"
                break
        
        return name
    
    def _calculate_required_trust(self, actions: List) -> int:
        """Calculate minimum trust level needed for skill"""
        if not actions:
            return 1
        
        return max((getattr(a, "required_trust", 1) for a in actions), default=1)
    
    def generalize_with_llm(self, pattern: CommandPattern) -> Dict[str, Any]:
        """
        Use local LLM to generalize pattern (future enhancement)
        
        Currently returns basic generalization.
        Future: Use Qwen2.5 to create better names, triggers, descriptions
        """
        # TODO: Implement LLM-based generalization
        # For now, use rule-based approach

        commands = pattern.commands
        # Guard: pattern may carry no sample commands (e.g. reconstructed from
        # a saved suggestion) — fall back to the representative command.
        example = commands[0] if commands else pattern.representative_command

        return {
            "name": pattern.suggested_name,
            "triggers": pattern.suggested_triggers,
            "description": f"Automates: {example}",
            "confidence": pattern.confidence,
        }
    
    def _normalize(self, command: str) -> str:
        """Normalize command"""
        return " ".join(command.lower().split())
    
    def review_and_approve(self, skill_id: str, approved: bool = True) -> Optional[Skill]:
        """Review auto-generated skill and approve/reject"""
        try:
            skill = self.skill_manager.get(skill_id)
            if not skill:
                return None
            
            from backend.skills.skill_schema import SkillStatus
            
            if approved:
                # Enable the skill
                skill = self.skill_manager.update(
                    skill_id,
                    status=SkillStatus.ENABLED.value,
                    metadata={**skill.metadata, "approved_at": self._now(), "approved": True}
                )
                logger.info(f"Approved auto-generated skill: {skill.name}")
            else:
                # Disable/delete
                skill = self.skill_manager.update(
                    skill_id,
                    status=SkillStatus.DISABLED.value,
                    metadata={**skill.metadata, "approved": False, "rejected_at": self._now()}
                )
                logger.info(f"Rejected auto-generated skill: {skill.name}")
            
            return skill
        except Exception as e:
            logger.error(f"Failed to review skill {skill_id}: {e}")
            return None
    
    def _now(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()