"""
JARVIS Telegram Gateway
Sprint 6: Control JARVIS from Telegram
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from backend.gateway.base import BaseGateway, GatewayMessage


class TelegramGateway(BaseGateway):
    """Telegram bot gateway for JARVIS"""

    def __init__(self, bot_token: Optional[str] = None, allowed_users: Optional[list] = None):
        super().__init__("telegram")
        self.bot_token = bot_token
        # Normalize to strings: Telegram user ids are ints on the wire, but
        # configs/JSON may contain either. Mixed types would silently deny
        # legitimate users (or worse, mask allowlist mistakes).
        self.allowed_users = {str(u) for u in (allowed_users or [])}
        self.app = None

    def _build_application(self):
        """Build the python-telegram-bot Application (separated for testability).

        Raises ImportError if python-telegram-bot is not installed.
        """
        from telegram import Update
        from telegram.ext import Application, ContextTypes, MessageHandler, filters

        app = Application.builder().token(self.bot_token).build()

        async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await self._process_update(update)

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        return app

    def _on_polling_error(self, exc: BaseException) -> None:
        """Called by PTB when the polling loop hits an error.

        PTB retries network errors internally; we just make sure failures are
        visible instead of dying silently.
        """
        logger.warning(f"Telegram polling error (library will retry): {exc}")

    async def start(self) -> bool:
        """Start Telegram bot"""
        if self.is_running:
            logger.debug("Telegram gateway already running")
            return True

        if not self.bot_token:
            logger.warning("Telegram bot token not configured")
            return False

        try:
            self.app = self._build_application()
        except ImportError:
            logger.error(
                "python-telegram-bot not installed. Run: pip install python-telegram-bot"
            )
            self.app = None
            return False
        except Exception as e:
            logger.error(f"Failed to build Telegram application: {type(e).__name__}: {e}")
            self.app = None
            return False

        try:
            await self.app.initialize()
            await self.app.start()
            # Awaited (not fire-and-forget): startup failures such as an
            # invalid token or no network surface here instead of being
            # swallowed by an unobserved asyncio task.
            await self.app.updater.start_polling(
                drop_pending_updates=True,
                error_callback=self._on_polling_error,
            )
            self.is_running = True
            logger.info("Telegram gateway started")
            return True
        except Exception as e:
            # Never log the token; exception text is safe, payloads are not.
            logger.error(f"Failed to start Telegram gateway: {type(e).__name__}: {e}")
            await self._cleanup_app()
            return False

    async def stop(self):
        """Stop Telegram bot (idempotent, tolerates partial startup)."""
        was_running = self.is_running or self.app is not None
        await self._cleanup_app()
        if was_running:
            logger.info("Telegram gateway stopped")

    async def _cleanup_app(self):
        """Tear down the PTB application. Each step is isolated so one
        failing stage (e.g. updater never started) doesn't leak the rest."""
        app, self.app = self.app, None
        self.is_running = False
        if app is None:
            return

        updater = getattr(app, "updater", None)
        if updater is not None:
            try:
                if getattr(updater, "running", True):
                    await updater.stop()
            except Exception as e:
                logger.debug(f"Telegram updater stop: {e}")
        try:
            if getattr(app, "running", True):
                await app.stop()
        except Exception as e:
            logger.debug(f"Telegram app stop: {e}")
        try:
            await app.shutdown()
        except Exception as e:
            logger.debug(f"Telegram app shutdown: {e}")

    async def send_message(self, user_id: str, text: str, **kwargs) -> bool:
        """Send message to Telegram user"""
        try:
            if not self.is_running or self.app is None:
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

    def is_user_allowed(self, user_id: str) -> bool:
        """Fail-closed allowlist check.

        SECURITY: an empty allowlist means NOBODY is authorized, not everybody.
        This gateway hands messages to an agent that controls the local PC, so
        access must be explicitly granted per user id.
        """
        return str(user_id) in self.allowed_users

    async def _process_update(self, update):
        """Process incoming Telegram update"""
        try:
            message = update.message
            if not message or not message.text:
                return
            if message.from_user is None:
                # Channel posts / anonymous admins have no user identity.
                return

            user_id = str(message.from_user.id)

            if not self.is_user_allowed(user_id):
                logger.warning(f"Unauthorized Telegram user: {user_id}")
                try:
                    await message.reply_text("You are not authorized to use this bot.")
                except Exception:
                    pass
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
