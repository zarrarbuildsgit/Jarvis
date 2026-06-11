"""
JARVIS Skill Self-Improvement System
Sprint 3: Skills that learn from failures and improve automatically
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.agent.trajectory import TrajectoryLogger
from backend.skills.skill_manager import SkillManager
from backend.skills.skill_schema import Skill, SkillStep


@dataclass
class SkillPerformance:
    """Tracks skill performance metrics"""
    
    skill_id: str
    total_runs: int = 0
    successes: int = 0
    failures: int = 0
    success_rate: float = 0.0
    avg_duration_ms: int = 0
    last_run: Optional[str] = None
    last_failure: Optional[str] = None
    failure_reasons: Dict[str, int] = field(default_factory=dict)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "total_runs": self.total_runs,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "last_run": self.last_run,
            "last_failure": self.last_failure,
            "failure_reasons": self.failure_reasons,
            "improvement_suggestions": self.improvement_suggestions,
        }


class SkillImprover:
    """Analyzes skill failures and proposes improvements"""
    
    def __init__(
        self,
        skill_manager: Optional[SkillManager] = None,
        trajectory_logger: Optional[TrajectoryLogger] = None,
    ):
        self.skill_manager = skill_manager or SkillManager()
        self.trajectory_logger = trajectory_logger or TrajectoryLogger()
        self.performance_file = "data/skills/performance.json"
    
    def track_execution(
        self,
        skill_id: str,
        success: bool,
        duration_ms: int = 0,
        error: Optional[str] = None,
        trajectory_id: Optional[str] = None,
    ):
        """Track a skill execution for performance monitoring"""
        try:
            perf = self._load_performance(skill_id)
            
            perf.total_runs += 1
            if success:
                perf.successes += 1
            else:
                perf.failures += 1
                perf.last_failure = self._now()
                if error:
                    # Track failure reasons
                    error_key = error[:100]  # Truncate long errors
                    perf.failure_reasons[error_key] = perf.failure_reasons.get(error_key, 0) + 1
            
            perf.success_rate = perf.successes / perf.total_runs if perf.total_runs > 0 else 0
            perf.last_run = self._now()
            
            # Update average duration
            if duration_ms > 0:
                if perf.avg_duration_ms == 0:
                    perf.avg_duration_ms = duration_ms
                else:
                    # Rolling average
                    perf.avg_duration_ms = int(
                        (perf.avg_duration_ms * (perf.total_runs - 1) + duration_ms) / perf.total_runs
                    )
            
            self._save_performance(perf)
            
            # Check if improvement needed
            if not success and perf.failures >= 2:
                self._analyze_failure(skill_id, error, trajectory_id)
            
            logger.debug(f"Tracked skill {skill_id}: success={success}, rate={perf.success_rate:.1%}")
            
        except Exception as e:
            logger.error(f"Failed to track skill execution: {e}")
    
    def _analyze_failure(
        self,
        skill_id: str,
        error: Optional[str],
        trajectory_id: Optional[str],
    ):
        """Analyze a skill failure and propose improvements"""
        try:
            skill = self.skill_manager.get(skill_id)
            if not skill:
                return
            
            perf = self._load_performance(skill_id)
            
            # Only analyze if we have enough data
            if perf.failures < 2 or perf.total_runs < 3:
                return
            
            # Get recent trajectories for this skill
            suggestions = []
            
            # Analyze failure patterns
            if perf.failure_reasons:
                most_common_error = max(perf.failure_reasons.items(), key=lambda x: x[1])
                error_text, count = most_common_error
                
                # Common failure patterns and suggestions
                if "not found" in error_text.lower() or "no such file" in error_text.lower():
                    suggestions.append("Add file existence check before action")
                    suggestions.append("Use fuzzy path matching")
                
                elif "timeout" in error_text.lower():
                    suggestions.append("Increase action timeout")
                    suggestions.append("Add retry logic")
                
                elif "permission" in error_text.lower() or "access denied" in error_text.lower():
                    suggestions.append("Check required trust level")
                    suggestions.append("Add permission check step")
                
                elif "blocked" in error_text.lower():
                    suggestions.append("Review safety policy")
                    suggestions.append("Request higher trust level")
                
                else:
                    suggestions.append(f"Investigate error: {error_text[:50]}")
            
            # Check success rate
            if perf.success_rate < 0.7 and perf.total_runs >= 5:
                suggestions.append("Consider breaking into smaller steps")
                suggestions.append("Add validation between steps")
            
            # Check if skill is slow
            if perf.avg_duration_ms > 5000:  # 5 seconds
                suggestions.append("Optimize slow actions")
                suggestions.append("Consider parallel execution")
            
            # Save suggestions
            if suggestions:
                perf.improvement_suggestions = list(set(suggestions))  # Deduplicate
                self._save_performance(perf)
                logger.info(f"Generated {len(suggestions)} improvement suggestions for skill {skill_id}")
                
                # Auto-create improvement if confidence high
                if perf.success_rate < 0.5 and perf.failures >= 3:
                    self._propose_improvement(skill, perf, error)
        
        except Exception as e:
            logger.error(f"Failed to analyze failure: {e}")
    
    def _propose_improvement(
        self,
        skill: Skill,
        perf: SkillPerformance,
        error: Optional[str],
    ):
        """Propose an automatic improvement to the skill"""
        try:
            # Create improved version
            improved_skill = self._create_improved_version(skill, perf, error)
            
            if improved_skill:
                # Save as new version (don't auto-enable)
                from backend.skills.skill_schema import SkillStatus
                
                # Mark as draft for review
                improved_skill = self.skill_manager.update(
                    improved_skill.id,
                    status=SkillStatus.DRAFT.value,
                    metadata={
                        **improved_skill.metadata,
                        "improved_from": skill.id,
                        "improvement_reason": f"Auto-improved after {perf.failures} failures",
                        "original_success_rate": perf.success_rate,
                        "improvement_date": self._now(),
                    }
                )
                
                logger.info(f"Created improved version of skill {skill.name}: {improved_skill.id}")
                return improved_skill
        
        except Exception as e:
            logger.error(f"Failed to propose improvement: {e}")
        
        return None
    
    def _create_improved_version(
        self,
        skill: Skill,
        perf: SkillPerformance,
        error: Optional[str],
    ) -> Optional[Skill]:
        """Create an improved version of a skill"""
        try:
            # Clone the skill
            import copy
            improved = copy.deepcopy(skill)
            improved.id = f"skill_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            improved.name = f"{skill.name}_v2"
            
            # Apply improvements based on failure analysis
            if error and "not found" in error.lower():
                # Add validation step
                for step in improved.steps:
                    step.notes = f"{step.notes} [Auto-added validation]".strip()
            
            if error and "timeout" in error.lower():
                # Increase timeouts
                for step in improved.steps:
                    step.action.timeout_seconds = min(
                        step.action.timeout_seconds * 1.5,
                        60.0  # Cap at 60s
                    )
            
            # Save improved version
            self.skill_manager._skills[improved.id] = improved
            self.skill_manager.save(improved)
            
            return improved
            
        except Exception as e:
            logger.error(f"Failed to create improved version: {e}")
            return None
    
    def get_performance(self, skill_id: str) -> SkillPerformance:
        """Get performance metrics for a skill"""
        return self._load_performance(skill_id)
    
    def get_all_performance(self) -> List[SkillPerformance]:
        """Get performance for all skills"""
        try:
            import json
            from pathlib import Path
            
            perf_file = Path(self.performance_file)
            if not perf_file.exists():
                return []
            
            data = json.loads(perf_file.read_text(encoding="utf-8"))
            return [SkillPerformance(**p) for p in data.get("performances", [])]
        except Exception as e:
            logger.error(f"Failed to load all performance: {e}")
            return []
    
    def _load_performance(self, skill_id: str) -> SkillPerformance:
        """Load performance data for a skill"""
        try:
            import json
            from pathlib import Path
            
            perf_file = Path(self.performance_file)
            if perf_file.exists():
                data = json.loads(perf_file.read_text(encoding="utf-8"))
                for p in data.get("performances", []):
                    if p.get("skill_id") == skill_id:
                        return SkillPerformance(**p)
            
            return SkillPerformance(skill_id=skill_id)
        except Exception as e:
            logger.error(f"Failed to load performance: {e}")
            return SkillPerformance(skill_id=skill_id)
    
    def _save_performance(self, perf: SkillPerformance):
        """Save performance data"""
        try:
            import json
            from pathlib import Path
            
            perf_file = Path(self.performance_file)
            perf_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing
            if perf_file.exists():
                data = json.loads(perf_file.read_text(encoding="utf-8"))
                performances = data.get("performances", [])
            else:
                performances = []
            
            # Update or add
            updated = False
            for i, p in enumerate(performances):
                if p.get("skill_id") == perf.skill_id:
                    performances[i] = perf.to_dict()
                    updated = True
                    break
            
            if not updated:
                performances.append(perf.to_dict())
            
            # Save
            data = {
                "updated_at": self._now(),
                "performances": performances
            }
            perf_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            
        except Exception as e:
            logger.error(f"Failed to save performance: {e}")
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()