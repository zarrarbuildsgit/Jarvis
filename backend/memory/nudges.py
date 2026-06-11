"""
JARVIS Memory Nudges System
Sprint 4: Daily reflection and user modeling
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.agent.trajectory import TrajectoryLogger
from backend.memory.preferences import PreferenceStore


class MemoryNudges:
    """Performs periodic reflection to extract insights and build user model"""
    
    def __init__(
        self,
        trajectory_logger: Optional[TrajectoryLogger] = None,
        preference_store: Optional[PreferenceStore] = None,
    ):
        self.trajectory_logger = trajectory_logger or TrajectoryLogger()
        self.preference_store = preference_store or PreferenceStore()
        self.memory_dir = Path("data/memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.user_md = self.memory_dir / "USER.md"
        self.memory_md = self.memory_dir / "MEMORY.md"
    
    def run_daily_nudge(self) -> Dict[str, Any]:
        """Run daily reflection to extract patterns and preferences"""
        try:
            logger.info("Running daily memory nudge...")
            
            yesterday = datetime.now() - timedelta(days=1)
            trajectories = self._get_trajectories_since(yesterday)
            
            if not trajectories:
                logger.info("No trajectories to analyze")
                return {"analyzed": 0, "insights": []}
            
            insights = self._extract_insights(trajectories)
            self._update_user_md(insights)
            self._update_memory_md(trajectories, insights)
            
            preferences = self._extract_preferences(trajectories)
            for pref in preferences:
                self.preference_store.ingest_text(pref, source="daily_nudge")
            
            result = {
                "analyzed": len(trajectories),
                "insights": insights,
                "preferences_extracted": len(preferences),
                "timestamp": self._now(),
            }
            
            logger.info(f"Daily nudge complete: {len(trajectories)} trajectories, {len(insights)} insights")
            return result
            
        except Exception as e:
            logger.error(f"Daily nudge failed: {e}")
            return {"error": str(e)}
    
    def _get_trajectories_since(self, since: datetime) -> List[Dict]:
        """Get trajectories since given time"""
        try:
            all_trajs = self.trajectory_logger.get_recent(limit=500)
            recent = []
            
            for traj in all_trajs:
                try:
                    traj_time = datetime.fromisoformat(traj["timestamp"].replace("Z", "+00:00"))
                    if traj_time.replace(tzinfo=None) >= since.replace(tzinfo=None):
                        recent.append(traj)
                except Exception:
                    continue
            
            return recent
        except Exception as e:
            logger.error(f"Failed to get trajectories: {e}")
            return []
    
    def _extract_insights(self, trajectories: List[Dict]) -> List[str]:
        """Extract insights from trajectories"""
        insights = []
        
        try:
            from collections import Counter
            commands = [t.get("command", "") for t in trajectories]
            command_counts = Counter(commands)
            
            if command_counts:
                top_commands = command_counts.most_common(3)
                for cmd, count in top_commands:
                    if count >= 2:
                        insights.append(f"Frequently used: '{cmd}' ({count} times)")
            
            successes = sum(1 for t in trajectories if t.get("success"))
            total = len(trajectories)
            if total > 0:
                rate = successes / total
                insights.append(f"Success rate: {rate:.0%} ({successes}/{total})")
            
            hours = []
            for traj in trajectories:
                try:
                    t = datetime.fromisoformat(traj["timestamp"].replace("Z", "+00:00"))
                    hours.append(t.hour)
                except Exception:
                    pass
            
            if hours:
                from collections import Counter
                hour_counts = Counter(hours)
                peak_hour = hour_counts.most_common(1)[0][0]
                insights.append(f"Most active hour: {peak_hour}:00")
            
            all_actions = []
            for traj in trajectories:
                for step in traj.get("steps", []):
                    action = step.get("action", {})
                    if action:
                        all_actions.append(action.get("type", ""))
            
            if all_actions:
                from collections import Counter
                action_counts = Counter(all_actions)
                top_action = action_counts.most_common(1)[0]
                insights.append(f"Most used action: {top_action[0]} ({top_action[1]} times)")
            
        except Exception as e:
            logger.error(f"Failed to extract insights: {e}")
        
        return insights
    
    def _extract_preferences(self, trajectories: List[Dict]) -> List[str]:
        """Extract user preferences from trajectories"""
        preferences = []
        
        try:
            commands = [t.get("command", "").lower() for t in trajectories]
            
            if any("dark" in cmd for cmd in commands):
                preferences.append("Prefers dark mode")
            
            if any("spotify" in cmd or "music" in cmd for cmd in commands):
                preferences.append("Listens to music while working")
            
            if any("chrome" in cmd for cmd in commands):
                preferences.append("Uses Chrome browser")
            
            if any("vscode" in cmd or "code" in cmd for cmd in commands):
                preferences.append("Uses VS Code")
            
            hours = []
            for traj in trajectories:
                try:
                    t = datetime.fromisoformat(traj["timestamp"].replace("Z", "+00:00"))
                    hours.append(t.hour)
                except Exception:
                    pass
            
            if hours:
                avg_hour = sum(hours) / len(hours)
                if 9 <= avg_hour <= 17:
                    preferences.append("Works during business hours")
                elif avg_hour < 9:
                    preferences.append("Early riser")
                else:
                    preferences.append("Night owl")
        
        except Exception as e:
            logger.error(f"Failed to extract preferences: {e}")
        
        return preferences
    
    def _update_user_md(self, insights: List[str]):
        """Update USER.md with insights"""
        try:
            content = []
            content.append("# User Profile")
            content.append("")
            content.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
            content.append("")
            
            try:
                prefs = self.preference_store.list()
                if prefs:
                    content.append("## Preferences")
                    content.append("")
                    for pref in prefs[:10]:
                        content.append(f"- {pref.value} (confidence: {pref.confidence:.0%})")
                    content.append("")
            except Exception:
                pass
            
            if insights:
                content.append("## Recent Activity")
                content.append("")
                for insight in insights:
                    content.append(f"- {insight}")
                content.append("")
            
            self.user_md.write_text("\n".join(content), encoding="utf-8")
            logger.debug(f"Updated USER.md")
            
        except Exception as e:
            logger.error(f"Failed to update USER.md: {e}")
    
    def _update_memory_md(self, trajectories: List[Dict], insights: List[str]):
        """Update MEMORY.md with learnings"""
        try:
            content = []
            content.append("# JARVIS Memory")
            content.append("")
            content.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
            content.append("")
            content.append("## Summary")
            content.append("")
            content.append(f"- Trajectories analyzed: {len(trajectories)}")
            content.append(f"- Insights generated: {len(insights)}")
            content.append("")
            
            if insights:
                content.append("## Recent Learnings")
                content.append("")
                for insight in insights:
                    content.append(f"- {insight}")
                content.append("")
            
            if self.memory_md.exists():
                existing = self.memory_md.read_text(encoding="utf-8")
                lines = existing.split("\n")
                if len(lines) > 50:
                    content.extend(["", "## History", ""])
                    content.extend(lines[-50:])
            
            self.memory_md.write_text("\n".join(content), encoding="utf-8")
            logger.debug(f"Updated MEMORY.md")
            
        except Exception as e:
            logger.error(f"Failed to update MEMORY.md: {e}")
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get current user profile"""
        try:
            profile = {
                "user_md_exists": self.user_md.exists(),
                "memory_md_exists": self.memory_md.exists(),
                "preferences_count": 0,
                "last_nudge": None,
            }
            
            if self.user_md.exists():
                content = self.user_md.read_text(encoding="utf-8")
                profile["user_md_preview"] = content[:500]
            
            try:
                prefs = self.preference_store.list()
                profile["preferences_count"] = len(prefs)
            except Exception:
                pass
            
            return profile
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return {}
    
    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()