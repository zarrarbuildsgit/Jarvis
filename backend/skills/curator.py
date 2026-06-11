"""
JARVIS Skill Curator
Sprint 2: Autonomous Skill Creation

Monitors task history and trajectories to detect patterns.
When 3+ similar commands are found, proposes a new skill.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from backend.agent.trajectory import TrajectoryLogger
from backend.tasks.history import TaskHistory


@dataclass
class CommandPattern:
    """Detected pattern of similar commands"""
    
    representative_command: str
    commands: List[str] = field(default_factory=list)
    count: int = 0
    first_seen: str = ""
    last_seen: str = ""
    avg_success_rate: float = 0.0
    suggested_name: str = ""
    suggested_triggers: List[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "representative_command": self.representative_command,
            "commands": self.commands,
            "count": self.count,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "avg_success_rate": self.avg_success_rate,
            "suggested_name": self.suggested_name,
            "suggested_triggers": self.suggested_triggers,
            "confidence": self.confidence,
        }


class SkillCurator:
    """Detects patterns in user behavior to suggest new skills"""
    
    def __init__(
        self,
        trajectory_logger: Optional[TrajectoryLogger] = None,
        task_history: Optional[TaskHistory] = None,
        min_occurrences: int = 3,
        lookback_days: int = 7,
        similarity_threshold: float = 0.7,
        data_dir: str = "data/skills",
    ):
        self.trajectory_logger = trajectory_logger or TrajectoryLogger()
        self.task_history = task_history or TaskHistory()
        self.min_occurrences = min_occurrences
        self.lookback_days = lookback_days
        self.similarity_threshold = similarity_threshold
        self.suggestions_file = Path(data_dir) / "suggestions.json"
        self.suggestions_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Parse an ISO timestamp into an aware UTC datetime.

        Trajectories on disk contain a mix of naive local timestamps and
        timezone-aware ones (with offset or trailing 'Z'). Naive values are
        assumed to be local time so comparisons never mix naive and aware.
        """
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.astimezone()  # interpret naive as local time
        return dt.astimezone(timezone.utc)
    
    def scan_for_patterns(self) -> List[CommandPattern]:
        """Scan recent trajectories for repeated command patterns"""
        try:
            # Get recent trajectories
            trajectories = self.trajectory_logger.get_recent(limit=200)
            
            if not trajectories:
                return []
            
            # Filter by date and success
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
            recent_successful = []

            for traj in trajectories:
                try:
                    traj_time = self._parse_timestamp(traj["timestamp"])
                    if traj_time < cutoff:
                        continue
                    if traj.get("success"):
                        recent_successful.append(traj)
                except Exception:
                    continue
            
            # Group by similarity
            patterns = self._cluster_commands(recent_successful)
            
            # Filter by minimum occurrences
            significant_patterns = [
                p for p in patterns 
                if p.count >= self.min_occurrences and p.confidence >= self.similarity_threshold
            ]
            
            # Sort by count (most frequent first)
            significant_patterns.sort(key=lambda p: p.count, reverse=True)
            
            logger.info(f"Curator found {len(significant_patterns)} patterns from {len(recent_successful)} trajectories")
            return significant_patterns
            
        except Exception as e:
            logger.error(f"Failed to scan for patterns: {e}")
            return []
    
    def _cluster_commands(self, trajectories: List[Dict]) -> List[CommandPattern]:
        """Group similar commands together"""
        # Simple clustering by normalized command similarity
        clusters: Dict[str, List[Dict]] = defaultdict(list)
        
        for traj in trajectories:
            command = traj.get("command", "").strip().lower()
            if not command:
                continue
            
            # Normalize command
            normalized = self._normalize_command(command)
            
            # Find existing cluster or create new
            matched = False
            for cluster_key in list(clusters.keys()):
                if self._commands_similar(normalized, cluster_key):
                    clusters[cluster_key].append(traj)
                    matched = True
                    break
            
            if not matched:
                clusters[normalized].append(traj)
        
        # Convert clusters to patterns
        patterns = []
        for cluster_key, trajs in clusters.items():
            if len(trajs) < 2:  # Need at least 2 to be a pattern
                continue
            
            commands = [t.get("command", "") for t in trajs]
            first_seen = min(t.get("timestamp", "") for t in trajs)
            last_seen = max(t.get("timestamp", "") for t in trajs)
            
            # Calculate success rate
            successes = sum(1 for t in trajs if t.get("success"))
            success_rate = successes / len(trajs) if trajs else 0
            
            # Generate suggestions
            suggested_name = self._suggest_name(commands)
            suggested_triggers = self._suggest_triggers(commands)
            confidence = self._calculate_confidence(trajs)
            
            pattern = CommandPattern(
                representative_command=trajs[0].get("command", ""),
                commands=commands,
                count=len(trajs),
                first_seen=first_seen,
                last_seen=last_seen,
                avg_success_rate=success_rate,
                suggested_name=suggested_name,
                suggested_triggers=suggested_triggers,
                confidence=confidence,
            )
            patterns.append(pattern)
        
        return patterns
    
    def _normalize_command(self, command: str) -> str:
        """Normalize command for comparison"""
        # Lowercase, remove extra spaces, remove common variations
        normalized = " ".join(command.lower().split())
        
        # Remove common filler words that don't change intent
        fillers = ["please", "could you", "can you", "would you", "hey jarvis", "jarvis"]
        for filler in fillers:
            normalized = normalized.replace(filler, "").strip()
        
        normalized = " ".join(normalized.split())  # Re-normalize spaces
        return normalized
    
    def _commands_similar(self, cmd1: str, cmd2: str) -> bool:
        """Check if two commands are similar enough to cluster"""
        # Simple similarity: Jaccard similarity of words
        words1 = set(cmd1.split())
        words2 = set(cmd2.split())
        
        if not words1 or not words2:
            return False
        
        intersection = words1 & words2
        union = words1 | words2
        
        similarity = len(intersection) / len(union) if union else 0
        return similarity >= self.similarity_threshold
    
    def _suggest_name(self, commands: List[str]) -> str:
        """Generate a skill name from commands"""
        if not commands:
            return "unnamed_skill"
        
        # Use most common words
        all_words = []
        for cmd in commands:
            words = self._normalize_command(cmd).split()
            # Filter out very common words
            filtered = [w for w in words if len(w) > 2 and w not in {"the", "and", "for", "with"}]
            all_words.extend(filtered)
        
        # Get most frequent meaningful words
        from collections import Counter
        word_counts = Counter(all_words)
        top_words = [w for w, _ in word_counts.most_common(3)]
        
        if top_words:
            return "_".join(top_words[:3])
        else:
            # Fallback: use first command, sanitized
            first = self._normalize_command(commands[0])
            return first.replace(" ", "_")[:30]
    
    def _suggest_triggers(self, commands: List[str]) -> List[str]:
        """Suggest trigger phrases from commands"""
        # Use the actual commands as triggers, deduplicated
        seen = set()
        triggers = []
        
        for cmd in commands:
            normalized = self._normalize_command(cmd)
            if normalized and normalized not in seen:
                seen.add(normalized)
                triggers.append(cmd)  # Keep original casing
                if len(triggers) >= 5:  # Limit to 5 triggers
                    break
        
        return triggers
    
    def _calculate_confidence(self, trajectories: List[Dict]) -> float:
        """Calculate confidence score for pattern"""
        if not trajectories:
            return 0.0
        
        # Factors:
        # 1. Consistency of commands (similarity)
        # 2. Success rate
        # 3. Recency
        # 4. Frequency
        
        commands = [t.get("command", "") for t in trajectories]
        normalized = [self._normalize_command(c) for c in commands]
        
        # Similarity score
        unique_normalized = len(set(normalized))
        similarity_score = 1.0 - (unique_normalized - 1) / len(normalized) if len(normalized) > 1 else 1.0
        
        # Success rate
        successes = sum(1 for t in trajectories if t.get("success"))
        success_rate = successes / len(trajectories) if trajectories else 0
        
        # Recency score (more recent = higher)
        try:
            last_time = max(self._parse_timestamp(t.get("timestamp", "")) for t in trajectories)
            days_ago = (datetime.now(timezone.utc) - last_time).days
            recency_score = max(0.0, min(1.0, 1.0 - days_ago / self.lookback_days))
        except Exception:
            recency_score = 0.5
        
        # Frequency score
        frequency_score = min(1.0, len(trajectories) / 10)  # Cap at 10 occurrences
        
        # Weighted average
        confidence = (
            similarity_score * 0.3 +
            success_rate * 0.3 +
            recency_score * 0.2 +
            frequency_score * 0.2
        )
        
        return round(confidence, 2)
    
    def get_suggestions(self) -> List[Dict[str, Any]]:
        """Get saved skill suggestions"""
        try:
            if self.suggestions_file.exists():
                data = json.loads(self.suggestions_file.read_text(encoding="utf-8"))
                return data.get("suggestions", [])
            return []
        except Exception as e:
            logger.error(f"Failed to load suggestions: {e}")
            return []
    
    def save_suggestions(self, patterns: List[CommandPattern]):
        """Save patterns as suggestions"""
        try:
            suggestions = [p.to_dict() for p in patterns]
            data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(suggestions),
                "suggestions": suggestions
            }
            self._write_suggestions(data)
            logger.info(f"Saved {len(suggestions)} skill suggestions")
        except Exception as e:
            logger.error(f"Failed to save suggestions: {e}")

    def dismiss_suggestion(self, representative_command: str):
        """Dismiss a suggestion (user doesn't want it)"""
        try:
            suggestions = self.get_suggestions()
            filtered = [
                s for s in suggestions
                if s.get("representative_command") != representative_command
            ]
            data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(filtered),
                "suggestions": filtered
            }
            self._write_suggestions(data)
        except Exception as e:
            logger.error(f"Failed to dismiss suggestion: {e}")

    def _write_suggestions(self, data: Dict[str, Any]) -> None:
        """Atomically write the suggestions file (write temp, then replace).

        Prevents readers from seeing a partially written/corrupt JSON file.
        """
        self.suggestions_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.suggestions_file.with_name(self.suggestions_file.name + ".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        os.replace(tmp_path, self.suggestions_file)