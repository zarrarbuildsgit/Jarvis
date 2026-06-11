"""
JARVIS Gateway Base
Sprint 6: Multi-platform messaging gateway
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger


@dataclass
class GatewayMessage:
    """Standardized message format across platforms"""
    
    platform: str  # telegram, discord, slack, etc.
    user_id: str
    username: Optional[str] = None
    text: str = ""
    message_id: Optional[str] = None
    chat_id: Optional[str] = None
    timestamp: str = ""
    raw_data: Dict[str, Any] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if self.raw_data is None:
            self.raw_data = {}


class BaseGateway(ABC):
    """Base class for all messaging platform gateways"""
    
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.is_running = False
        self.message_handler = None
    
    @abstractmethod
    async def start(self):
        """Start the gateway"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the gateway"""
        pass
    
    @abstractmethod
    async def send_message(self, user_id: str, text: str, **kwargs) -> bool:
        """Send message to user"""
        pass
    
    def set_message_handler(self, handler):
        """Set callback for incoming messages"""
        self.message_handler = handler
    
    async def handle_incoming(self, message: GatewayMessage):
        """Process incoming message"""
        if self.message_handler:
            try:
                await self.message_handler(message)
            except Exception as e:
                logger.error(f"Error handling message in {self.platform_name}: {e}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform_name,
            "is_running": self.is_running,
        }