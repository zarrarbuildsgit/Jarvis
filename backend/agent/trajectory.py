"""
JARVIS Trajectory Logging System
Sprint 1: Foundation for self-improvement

Records full execution traces for every agent interaction:
prompt → thought → action → observation → result

Compatible with:
- Hermes agent format
- GEPA (Genetic-Pareto Prompt Evolution)
- DSPy trajectory format
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from backend.agent.action_schema import ActionPlan, ActionResult, RuntimeResult


@dataclass(slots=True)
class TrajectoryStep:
    """Single step in a trajectory: thought → action → observation"""
    
    step_number: int
    timestamp: str
    thought: str = ""  # Agent's reasoning
    action: Optional[Dict[str, Any]] = None
    observation: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Trajectory:
    """Complete execution trace for one command"""
    
    id: str = field(default_factory=lambda: f"traj_{uuid4().hex[:12]}")
    command: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    plan: Optional[Dict[str, Any]] = None
    steps: List[TrajectoryStep] = field(default_factory=list)
    final_result: Optional[Dict[str, Any]] = None
    success: bool = False
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "command": self.command,
            "timestamp": self.timestamp,
            "plan": self.plan,
            "steps": [s.to_dict() for s in self.steps],
            "final_result": self.final_result,
            "success": self.success,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }
    
    def to_jsonl(self) -> str:
        """Export as JSONL for GEPA/DSPy compatibility"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class TrajectoryLogger:
    """Logs trajectories to disk for analysis and learning"""
    
    def __init__(self, base_dir: str = "data/trajectories"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.current_trajectory: Optional[Trajectory] = None
        self.start_time: Optional[datetime] = None
    
    def start(self, command: str, plan: Optional[ActionPlan] = None, metadata: Optional[Dict] = None) -> str:
        """Start logging a new trajectory"""
        self.start_time = datetime.now()
        self.current_trajectory = Trajectory(
            command=command,
            plan=plan.to_dict() if plan else None,
            metadata=metadata or {}
        )
        logger.debug(f"Trajectory started: {self.current_trajectory.id} for command: {command}")
        return self.current_trajectory.id
    
    def log_step(
        self,
        thought: str = "",
        action: Optional[Dict] = None,
        observation: Optional[Dict] = None,
        result: Optional[ActionResult] = None
    ):
        """Log a single step in the current trajectory"""
        if not self.current_trajectory:
            logger.warning("No active trajectory to log step")
            return
        
        step = TrajectoryStep(
            step_number=len(self.current_trajectory.steps) + 1,
            timestamp=datetime.now().isoformat(),
            thought=thought,
            action=action,
            observation=observation,
            result=result.to_dict() if result else None
        )
        self.current_trajectory.steps.append(step)
    
    def finish(self, runtime_result: RuntimeResult) -> Trajectory:
        """Finish current trajectory and save to disk"""
        if not self.current_trajectory:
            logger.warning("No active trajectory to finish")
            return None
        
        end_time = datetime.now()
        if self.start_time:
            duration = (end_time - self.start_time).total_seconds() * 1000
            self.current_trajectory.duration_ms = int(duration)
        
        self.current_trajectory.final_result = runtime_result.to_dict()
        self.current_trajectory.success = runtime_result.success
        
        # Save to disk
        self._save_trajectory(self.current_trajectory)
        
        trajectory = self.current_trajectory
        self.current_trajectory = None
        self.start_time = None
        
        logger.info(f"Trajectory completed: {trajectory.id} success={trajectory.success} steps={len(trajectory.steps)}")
        return trajectory
    
    def _save_trajectory(self, trajectory: Trajectory):
        """Save trajectory to JSONL file"""
        try:
            # Daily rotation: trajectories-2026-06-09.jsonl
            date_str = datetime.now().strftime("%Y-%m-%d")
            file_path = self.base_dir / f"trajectories-{date_str}.jsonl"
            
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(trajectory.to_jsonl() + "\n")
            
            # Also save individual file for easy access
            individual_path = self.base_dir / f"{trajectory.id}.json"
            with open(individual_path, "w", encoding="utf-8") as f:
                json.dump(trajectory.to_dict(), f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save trajectory {trajectory.id}: {e}")
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent trajectories"""
        try:
            trajectories = []
            # Get all individual JSON files, sorted by modification time
            files = sorted(
                self.base_dir.glob("traj_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            for file_path in files[:limit]:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        trajectories.append(json.load(f))
                except Exception as e:
                    logger.warning(f"Failed to load trajectory {file_path}: {e}")
            
            return trajectories
        except Exception as e:
            logger.error(f"Failed to get recent trajectories: {e}")
            return []
    
    def get_by_id(self, trajectory_id: str) -> Optional[Dict[str, Any]]:
        """Get specific trajectory by ID"""
        try:
            file_path = self.base_dir / f"{trajectory_id}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to get trajectory {trajectory_id}: {e}")
            return None
    
    def export_for_gepa(self, output_path: str, limit: Optional[int] = None) -> int:
        """Export trajectories in GEPA-compatible format"""
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            count = 0
            with open(output_file, "w", encoding="utf-8") as out_f:
                # Get all trajectory files
                files = sorted(
                    self.base_dir.glob("traj_*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True
                )
                
                if limit:
                    files = files[:limit]
                
                for file_path in files:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            traj = json.load(f)
                            # GEPA format: simplified for skill evolution
                            gepa_entry = {
                                "input": traj["command"],
                                "output": traj["final_result"]["message"] if traj["final_result"] else "",
                                "success": traj["success"],
                                "steps": len(traj["steps"]),
                                "trajectory_id": traj["id"],
                                "timestamp": traj["timestamp"]
                            }
                            out_f.write(json.dumps(gepa_entry, ensure_ascii=False) + "\n")
                            count += 1
                    except Exception as e:
                        logger.warning(f"Failed to export {file_path}: {e}")
            
            logger.info(f"Exported {count} trajectories to {output_path}")
            return count
        except Exception as e:
            logger.error(f"Failed to export trajectories: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get trajectory statistics"""
        try:
            files = list(self.base_dir.glob("traj_*.json"))
            total = len(files)
            
            if total == 0:
                return {"total": 0, "success_rate": 0, "avg_steps": 0, "avg_duration_ms": 0}
            
            successes = 0
            total_steps = 0
            total_duration = 0
            
            for file_path in files[-100:]:  # Last 100 for performance
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        traj = json.load(f)
                        if traj.get("success"):
                            successes += 1
                        total_steps += len(traj.get("steps", []))
                        total_duration += traj.get("duration_ms", 0)
                except Exception:
                    pass
            
            sample_size = min(total, 100)
            return {
                "total": total,
                "success_rate": round(successes / sample_size * 100, 1) if sample_size > 0 else 0,
                "avg_steps": round(total_steps / sample_size, 1) if sample_size > 0 else 0,
                "avg_duration_ms": round(total_duration / sample_size) if sample_size > 0 else 0,
                "sample_size": sample_size
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total": 0, "success_rate": 0, "avg_steps": 0, "avg_duration_ms": 0}