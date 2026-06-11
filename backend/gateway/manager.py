"""
JARVIS Gateway Manager
Sprint 6: Manages all messaging platform gateways
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from backend.gateway.base import BaseGateway, GatewayMessage
from backend.gateway.telegram import TelegramGateway


class GatewayManager:
    """Manages all messaging gateways"""
    
    def __init__(self, config_file: str = "data/gateway/config.json"):
        self.config_file = Path(config_file)
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.gateways: Dict[str, BaseGateway] = {}
        self.message_handler = None
        self.load_config()
    
    def load_config(self):
        """Load gateway configuration"""
        try:
            if self.config_file.exists():
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
                
                # Initialize Telegram if configured
                telegram_config = config.get("telegram", {})
                if telegram_config.get("enabled") and telegram_config.get("bot_token"):
                    gateway = TelegramGateway(
                        bot_token=telegram_config["bot_token"],
                        allowed_users=telegram_config.get("allowed_users", [])
                    )
                    self.gateways["telegram"] = gateway
                    logger.info("Telegram gateway loaded from config")
        except Exception as e:
            logger.error(f"Failed to load gateway config: {e}")
    
    def save_config(self):
        """Save gateway configuration"""
        try:
            config = {}
            for name, gateway in self.gateways.items():
                if isinstance(gateway, TelegramGateway):
                    config[name] = {
                        "enabled": gateway.is_running,
                        "bot_token": gateway.bot_token,
                        "allowed_users": list(gateway.allowed_users),
                    }
            
            self.config_file.write_text(
                json.dumps(config, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save gateway config: {e}")
    
    def add_telegram(self, bot_token: str, allowed_users: Optional[List[str]] = None) -> TelegramGateway:
        """Add Telegram gateway"""
        gateway = TelegramGateway(bot_token, allowed_users)
        gateway.set_message_handler(self._handle_message)
        self.gateways["telegram"] = gateway
        self.save_config()
        return gateway
    
    def get_gateway(self, platform: str) -> Optional[BaseGateway]:
        """Get gateway by platform name"""
        return self.gateways.get(platform)
    
    def list_gateways(self) -> List[Dict[str, Any]]:
        """List all gateways"""
        return [gw.to_dict() for gw in self.gateways.values()]
    
    async def start_all(self):
        """Start all configured gateways"""
        for name, gateway in self.gateways.items():
            try:
                gateway.set_message_handler(self._handle_message)
                success = await gateway.start()
                if success:
                    logger.info(f"Started {name} gateway")
                else:
                    logger.warning(f"Failed to start {name} gateway")
            except Exception as e:
                logger.error(f"Error starting {name} gateway: {e}")
    
    async def stop_all(self):
        """Stop all gateways"""
        for name, gateway in self.gateways.items():
            try:
                await gateway.stop()
                logger.info(f"Stopped {name} gateway")
            except Exception as e:
                logger.error(f"Error stopping {name} gateway: {e}")
    
    async def send_message(self, platform: str, user_id: str, text: str, **kwargs) -> bool:
        """Send message via specified gateway"""
        gateway = self.get_gateway(platform)
        if not gateway:
            logger.error(f"Gateway not found: {platform}")
            return False
        
        return await gateway.send_message(user_id, text, **kwargs)
    
    def set_message_handler(self, handler):
        """Set global message handler"""
        self.message_handler = handler
        # Update all existing gateways
        for gateway in self.gateways.values():
            gateway.set_message_handler(handler)
    
    async def _handle_message(self, message: GatewayMessage):
        """Handle incoming message from any gateway"""
        if self.message_handler:
            try:
                await self.message_handler(message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
        else:
            logger.warning(f"No message handler set, dropping message from {message.platform}")