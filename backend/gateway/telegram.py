"""
JARVIS Telegram Gateway
Sprint 6: Control JARVIS from Telegram
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger

from backend.gateway.base import BaseGateway, GatewayMessage


class TelegramGateway(BaseGateway):
    """Telegram bot gateway for JARVIS"""
    
    def __init__(self, bot_token: Optional[str] = None, allowed_users: Optional[list] = None):
        super().__init__("telegram")
        self.bot_token = bot_token
        self.allowed_users = set(allowed_users or [])
        self.bot = None
        self.polling_task = None
    
    async def start(self):
        """Start Telegram bot"""
        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False
        
        try:
            # Import here to avoid dependency if not used
            from telegram import Update
            from telegram.ext import Application, MessageHandler, filters, ContextTypes
            
            # Create application
            self.app = Application.builder().token(self.bot_token).build()
            
            # Add message handler
            async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await self._process_update(update)
            
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            
            # Start polling
            await self.app.initialize()
            await self.app.start()
            
            self.polling_task = asyncio.create_task(self.app.updater.start_polling())
            self.is_running = True
            
            logger.info("Telegram gateway started")
            return True
            
        except ImportError:
            logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return False
        except Exception as e:
            logger.error(f"Failed to start Telegram gateway: {e}")
            return False
    
    async def stop(self):
        """Stop Telegram bot"""
        try:
            self.is_running = False
            
            if self.polling_task:
                self.polling_task.cancel()
            
            if hasattr(self, 'app'):
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            
            logger.info("Telegram gateway stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram gateway: {e}")
    
    async def send_message(self, user_id: str, text: str, **kwargs) -> bool:
        """Send message to Telegram user"""
        try:
            if not self.is_running or not hasattr(self, 'app'):
                return False
            
            await self.app.bot.send_message(
                chat_id=int(user_id),
                text=text,
                **kwargs
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def _process_update(self, update):
        """Process incoming Telegram update"""
        try:
            message = update.message
            if not message or not message.text:
                return
            
            user_id = str(message.from_user.id)
            
            # Check if user is allowed
            if self.allowed_users and user_id not in self.allowed_users:
                logger.warning(f"Unauthorized Telegram user: {user_id}")
                await message.reply_text("❌ You are not authorized to use this bot.")
                return
            
            # Create standardized message
            gateway_msg = GatewayMessage(
                platform="telegram",
                user_id=user_id,
                username=message.from_user.username,
                text=message.text,
                message_id=str(message.message_id),
                chat_id=str(message.chat_id),
                raw_data=update.to_dict(),
            )
            
            # Handle the message
            await self.handle_incoming(gateway_msg)
            
        except Exception as e:
            logger.error(f"Error processing Telegram update: {e}")
    
    def add_allowed_user(self, user_id: str):
        """Add user to allowed list"""
        self.allowed_users.add(str(user_id))
    
    def remove_allowed_user(self, user_id: str):
        """Remove user from allowed list"""
        self.allowed_users.discard(str(user_id))
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "allowed_users_count": len(self.allowed_users),
            "has_token": bool(self.bot_token),
        })
        return base