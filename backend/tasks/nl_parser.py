"""
JARVIS Natural Language Cron Parser
Sprint 5: Parse "every morning at 9am" into schedules
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from loguru import logger


class NaturalLanguageParser:
    """Parses natural language time expressions into schedules"""
    
    def __init__(self):
        # Common patterns - ORDER MATTERS (most specific first)
        self.patterns = {
            "every_interval": re.compile(
                r"every\s+(\d+)\s*(minute|hour|day)s?",
                re.IGNORECASE
            ),
            "in_duration": re.compile(
                r"in\s+(\d+)\s*(minute|hour|day|week)s?",
                re.IGNORECASE
            ),
            "every_weekday": re.compile(
                r"every\s+weekday(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
                re.IGNORECASE
            ),
            "every_morning": re.compile(
                r"every\s+morning(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
                re.IGNORECASE
            ),
            "every_evening": re.compile(
                r"every\s+evening(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
                re.IGNORECASE
            ),
            "every_day_at": re.compile(
                r"every\s+(?:day\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
                re.IGNORECASE
            ),
            "at_time": re.compile(
                r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)",
                re.IGNORECASE
            ),
        }
    
    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse natural language into schedule
        
        Returns:
            {
                "type": "daily" | "interval" | "once" | "delay",
                "time": "09:00" (for daily),
                "seconds": 3600 (for interval/delay),
                "cron": "0 9 * * *" (optional),
                "description": "Every day at 9:00 AM"
            }
        """
        text = text.lower().strip()
        
        # Try each pattern
        for pattern_name, pattern in self.patterns.items():
            match = pattern.search(text)
            if match:
                result = self._handle_match(pattern_name, match, text)
                if result:
                    return result
        
        return None
    
    def _handle_match(self, pattern_name: str, match, original_text: str) -> Optional[Dict]:
        """Handle a matched pattern"""
        try:
            if pattern_name == "every_day_at":
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                ampm = match.group(3)
                
                if ampm:
                    hour = self._to_24h(hour, ampm)
                
                return {
                    "type": "daily",
                    "time": f"{hour:02d}:{minute:02d}",
                    "cron": f"{minute} {hour} * * *",
                    "description": f"Every day at {self._format_time(hour, minute)}",
                }
            
            elif pattern_name == "every_morning":
                hour = match.group(1)
                if hour:
                    hour = int(hour)
                    minute = int(match.group(2) or 0)
                    ampm = match.group(3)
                    if ampm:
                        hour = self._to_24h(hour, ampm)
                else:
                    hour, minute = 9, 0  # Default morning
                
                return {
                    "type": "daily",
                    "time": f"{hour:02d}:{minute:02d}",
                    "cron": f"{minute} {hour} * * *",
                    "description": f"Every morning at {self._format_time(hour, minute)}",
                }
            
            elif pattern_name == "every_evening":
                hour = match.group(1)
                if hour:
                    hour = int(hour)
                    minute = int(match.group(2) or 0)
                    ampm = match.group(3)
                    if ampm:
                        hour = self._to_24h(hour, ampm)
                else:
                    hour, minute = 18, 0  # Default evening (6pm)
                
                return {
                    "type": "daily",
                    "time": f"{hour:02d}:{minute:02d}",
                    "cron": f"{minute} {hour} * * *",
                    "description": f"Every evening at {self._format_time(hour, minute)}",
                }
            
            elif pattern_name == "every_weekday":
                hour = match.group(1)
                if hour:
                    hour = int(hour)
                    minute = int(match.group(2) or 0)
                    ampm = match.group(3)
                    if ampm:
                        hour = self._to_24h(hour, ampm)
                else:
                    hour, minute = 9, 0
                
                return {
                    "type": "daily",
                    "time": f"{hour:02d}:{minute:02d}",
                    "cron": f"{minute} {hour} * * 1-5",
                    "description": f"Every weekday at {self._format_time(hour, minute)}",
                }
            
            elif pattern_name == "in_duration":
                amount = int(match.group(1))
                unit = match.group(2).lower()
                
                seconds = self._to_seconds(amount, unit)
                
                return {
                    "type": "delay",
                    "seconds": seconds,
                    "description": f"In {amount} {unit}{'s' if amount != 1 else ''}",
                }
            
            elif pattern_name == "every_interval":
                amount = int(match.group(1))
                unit = match.group(2).lower()
                
                seconds = self._to_seconds(amount, unit)
                
                return {
                    "type": "interval",
                    "seconds": seconds,
                    "description": f"Every {amount} {unit}{'s' if amount != 1 else ''}",
                }
            
            elif pattern_name == "at_time":
                hour = int(match.group(1))
                minute = int(match.group(2) or 0)
                ampm = match.group(3)
                
                hour = self._to_24h(hour, ampm)
                
                # Calculate next occurrence
                now = datetime.now()
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                
                return {
                    "type": "once",
                    "run_at": target.isoformat(),
                    "description": f"At {self._format_time(hour, minute)}",
                }
        
        except Exception as e:
            logger.error(f"Failed to handle pattern {pattern_name}: {e}")
            return None
        
        return None
    
    def _to_24h(self, hour: int, ampm: str) -> int:
        """Convert 12h to 24h"""
        ampm = ampm.lower()
        if ampm == "pm" and hour != 12:
            return hour + 12
        elif ampm == "am" and hour == 12:
            return 0
        return hour
    
    def _to_seconds(self, amount: int, unit: str) -> int:
        """Convert to seconds"""
        unit = unit.lower()
        if unit.startswith("minute"):
            return amount * 60
        elif unit.startswith("hour"):
            return amount * 3600
        elif unit.startswith("day"):
            return amount * 86400
        elif unit.startswith("week"):
            return amount * 604800
        return amount
    
    def _format_time(self, hour: int, minute: int) -> str:
        """Format time for display"""
        if hour == 0:
            return f"12:{minute:02d} AM"
        elif hour < 12:
            return f"{hour}:{minute:02d} AM"
        elif hour == 12:
            return f"12:{minute:02d} PM"
        else:
            return f"{hour-12}:{minute:02d} PM"
    
    def extract_schedule_from_command(self, command: str) -> Tuple[Optional[Dict], str]:
        """
        Extract schedule from command like:
        "every morning at 9am check email"
        
        Returns: (schedule_dict, remaining_command)
        """
        # Try to find schedule at start
        for pattern_name, pattern in self.patterns.items():
            match = pattern.search(command)
            if match:
                # Check if match is at beginning
                if match.start() < 10:  # Within first 10 chars
                    schedule = self._handle_match(pattern_name, match, command)
                    if schedule:
                        # Remove the schedule part from command
                        remaining = command[match.end():].strip()
                        # Clean up common separators
                        remaining = re.sub(r"^(to|and|then|,)\s+", "", remaining, flags=re.IGNORECASE)
                        return schedule, remaining
        
        return None, command