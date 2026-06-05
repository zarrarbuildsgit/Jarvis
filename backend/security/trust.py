"""
JARVIS Security Module - Trust Level System
"""

from pathlib import Path
import json
from loguru import logger
from datetime import datetime

class TrustManager:
    def __init__(self, trust_file: str = "data/security/trust_state.json"):
        self.trust_file = Path(trust_file)
        self.trust_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
    
    def _load_state(self) -> dict:
        """Load trust state from file"""
        if self.trust_file.exists():
            with open(self.trust_file, 'r') as f:
                return json.load(f)
        return {
            "current_level": 1,
            "max_level": 4,
            "history": [],
            "approved_actions": [],
            "denied_actions": [],
            "pending_review": [],
            "last_updated": datetime.now().isoformat()
        }
    
    def _save_state(self):
        """Save trust state to file"""
        self.state["last_updated"] = datetime.now().isoformat()
        with open(self.trust_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_current_level(self) -> int:
        return self.state["current_level"]
    
    def set_level(self, level: int, reason: str = "") -> bool:
        """Set trust level (only increase)"""
        if level > self.state["max_level"]:
            logger.error(f"Cannot set trust level above {self.state['max_level']}")
            return False
        
        if level < self.state["current_level"]:
            logger.error("Cannot decrease trust level manually")
            return False
        
        if level == self.state["current_level"]:
            return True
        
        old_level = self.state["current_level"]
        self.state["current_level"] = level
        self.state["history"].append({
            "from": old_level,
            "to": level,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_state()
        logger.info(f"Trust level increased from {old_level} to {level}: {reason}")
        return True
    
    def record_action(self, action: str, outcome: str, success: bool):
        """Record an action for trust evaluation"""
        entry = {
            "action": action,
            "outcome": outcome,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        if success:
            self.state["approved_actions"].append(entry)
        else:
            self.state["denied_actions"].append(entry)
        
        self._save_state()
        logger.debug(f"Action recorded: {action} -> {'Success' if success else 'Failed'}")
    
    def evaluate_trust(self) -> int:
        """Evaluate if trust level should be increased"""
        if self.state["current_level"] >= self.state["max_level"]:
            return self.state["current_level"]
        
        approved = len(self.state.get("approved_actions", []))
        denied = len(self.state.get("denied_actions", []))
        total = approved + denied
        
        if total == 0:
            return self.state["current_level"]
        
        success_rate = approved / total
        current_level = self.state["current_level"]
        
        if current_level == 1 and success_rate >= 0.9 and approved >= 10:
            self.set_level(2, f"Auto-promoted: {approved} successful ({success_rate:.0%} rate)")
        elif current_level == 2 and success_rate >= 0.95 and approved >= 50:
            self.set_level(3, f"Auto-promoted: {approved} successful ({success_rate:.0%} rate)")
        elif current_level == 3 and success_rate >= 0.98 and approved >= 200:
            self.set_level(4, f"Auto-promoted: {approved} successful ({success_rate:.0%} rate)")
        
        return self.state["current_level"]
    
    def reset_trust(self, reason: str = "Manual reset"):
        """Reset trust to level 1"""
        old_level = self.state["current_level"]
        self.state["current_level"] = 1
        self.state["history"].append({
            "from": old_level, "to": 1,
            "reason": reason, "timestamp": datetime.now().isoformat()
        })
        self._save_state()
        logger.warning(f"Trust reset to level 1: {reason}")
    
    def get_trust_summary(self) -> dict:
        return {
            "current_level": self.state["current_level"],
            "max_level": self.state["max_level"],
            "total_actions": len(self.state.get("approved_actions", [])) + len(self.state.get("denied_actions", [])),
            "successful": len(self.state.get("approved_actions", [])),
            "failed": len(self.state.get("denied_actions", [])),
            "history_count": len(self.state.get("history", []))
        }
