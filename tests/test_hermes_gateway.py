"""Tests for the multi-platform gateway subsystem (backend/gateway).

All tests are fully offline:
- python-telegram-bot is never imported (transport is mocked via
  TelegramGateway._build_application).
- No real bot token, no network.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.gateway.base import GatewayMessage
from backend.gateway.manager import GatewayManager
from backend.gateway.telegram import TelegramGateway

FAKE_TOKEN = "0000000000:TEST-FAKE-TOKEN-NOT-REAL"


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

class FakeUpdater:
    def __init__(self):
        self.running = False
        self.start_polling = AsyncMock(side_effect=self._start)
        self.stop = AsyncMock(side_effect=self._stop)

    async def _start(self, **kwargs):
        self.running = True

    async def _stop(self):
        self.running = False


class FakeApp:
    """Mock of python-telegram-bot's Application."""

    def __init__(self, fail_on=None):
        self.running = False
        self.fail_on = fail_on  # name of coroutine that should blow up
        self.updater = FakeUpdater()
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.calls = []

    async def initialize(self):
        self.calls.append("initialize")
        if self.fail_on == "initialize":
            raise ConnectionError("simulated network failure")

    async def start(self):
        self.calls.append("start")
        self.running = True
        if self.fail_on == "start":
            raise ConnectionError("simulated network failure")

    async def stop(self):
        self.calls.append("stop")
        self.running = False

    async def shutdown(self):
        self.calls.append("shutdown")


def make_gateway(allowed_users=None, app=None, token=FAKE_TOKEN):
    gw = TelegramGateway(bot_token=token, allowed_users=allowed_users)
    fake_app = app or FakeApp()
    gw._build_application = lambda: fake_app
    return gw, fake_app


def make_update(user_id=12345, text="hello", username="alice"):
    """Build a minimal fake telegram Update."""
    message = SimpleNamespace(
        text=text,
        from_user=SimpleNamespace(id=user_id, username=username),
        message_id=1,
        chat_id=user_id,
        reply_text=AsyncMock(),
    )
    return SimpleNamespace(message=message, to_dict=lambda: {"update_id": 1})


# ---------------------------------------------------------------------------
# Manager: add / get / list / persistence round-trip
# ---------------------------------------------------------------------------

class TestManagerPersistence:
    def test_add_get_list(self, tmp_path):
        manager = GatewayManager(config_file=str(tmp_path / "gw" / "config.json"))
        gateway = manager.add_telegram(FAKE_TOKEN, allowed_users=["111"])

        assert manager.get_gateway("telegram") is gateway
        assert manager.get_gateway("discord") is None

        listed = manager.list_gateways()
        assert len(listed) == 1
        assert listed[0]["platform"] == "telegram"
        assert listed[0]["is_running"] is False
        assert listed[0]["has_token"] is True
        # Token must never appear in the listing payload.
        assert FAKE_TOKEN not in json.dumps(listed)

    def test_persistence_round_trip(self, tmp_path):
        config_file = tmp_path / "gw" / "config.json"
        manager = GatewayManager(config_file=str(config_file))
        # Mixed int/str ids, gateway never started (regression: config used to
        # be saved with enabled=False and silently dropped on restart).
        manager.add_telegram(FAKE_TOKEN, allowed_users=[111, "222"])

        assert config_file.exists()
        saved = json.loads(config_file.read_text(encoding="utf-8"))
        assert saved["telegram"]["enabled"] is True
        assert saved["telegram"]["bot_token"] == FAKE_TOKEN

        # Fresh manager pointed at the same file must restore the gateway.
        manager2 = GatewayManager(config_file=str(config_file))
        gateway2 = manager2.get_gateway("telegram")
        assert gateway2 is not None
        assert gateway2.bot_token == FAKE_TOKEN
        assert gateway2.allowed_users == {"111", "222"}
        # Loaded gateways must be wired to the manager dispatcher so that
        # starting them directly does not drop incoming messages.
        assert gateway2.message_handler is not None

    def test_no_config_file_yields_empty_manager(self, tmp_path):
        manager = GatewayManager(config_file=str(tmp_path / "missing.json"))
        assert manager.list_gateways() == []

    def test_corrupt_config_does_not_crash(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("{not valid json", encoding="utf-8")
        manager = GatewayManager(config_file=str(config_file))
        assert manager.list_gateways() == []

    @pytest.mark.asyncio
    async def test_manager_dispatches_to_global_handler(self, tmp_path):
        manager = GatewayManager(config_file=str(tmp_path / "config.json"))
        gateway = manager.add_telegram(FAKE_TOKEN, allowed_users=["12345"])

        received = []

        async def handler(msg):
            received.append(msg)

        manager.set_message_handler(handler)
        await gateway._process_update(make_update(user_id=12345, text="status"))

        assert len(received) == 1
        assert isinstance(received[0], GatewayMessage)
        assert received[0].text == "status"
        assert received[0].platform == "telegram"


# ---------------------------------------------------------------------------
# Allowlist enforcement (security critical)
# ---------------------------------------------------------------------------

class TestAllowlistEnforcement:
    @pytest.mark.asyncio
    async def test_authorized_user_is_handled(self):
        gw, _ = make_gateway(allowed_users=["12345"])
        handler = AsyncMock()
        gw.set_message_handler(handler)

        await gw._process_update(make_update(user_id=12345, text="open notepad"))

        handler.assert_awaited_once()
        msg = handler.await_args.args[0]
        assert msg.user_id == "12345"
        assert msg.text == "open notepad"

    @pytest.mark.asyncio
    async def test_unauthorized_user_is_rejected(self):
        gw, _ = make_gateway(allowed_users=["12345"])
        handler = AsyncMock()
        gw.set_message_handler(handler)

        update = make_update(user_id=99999, text="rm -rf /")
        await gw._process_update(update)

        handler.assert_not_awaited()
        update.message.reply_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_allowlist_fails_closed(self):
        """SECURITY regression: empty allowlist must deny everyone,
        not allow everyone."""
        gw, _ = make_gateway(allowed_users=[])
        handler = AsyncMock()
        gw.set_message_handler(handler)

        await gw._process_update(make_update(user_id=42, text="shutdown the pc"))

        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_int_configured_allowlist_matches_wire_id(self):
        """Telegram sends int ids; configs may store ints. Must still match."""
        gw, _ = make_gateway(allowed_users=[12345])
        handler = AsyncMock()
        gw.set_message_handler(handler)

        await gw._process_update(make_update(user_id=12345))
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_without_user_identity_is_dropped(self):
        gw, _ = make_gateway(allowed_users=["12345"])
        handler = AsyncMock()
        gw.set_message_handler(handler)

        update = make_update()
        update.message.from_user = None  # channel post / anonymous admin
        await gw._process_update(update)

        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_or_missing_message_is_ignored(self):
        gw, _ = make_gateway(allowed_users=["12345"])
        handler = AsyncMock()
        gw.set_message_handler(handler)

        await gw._process_update(SimpleNamespace(message=None))
        update = make_update(text="")
        await gw._process_update(update)

        handler.assert_not_awaited()

    def test_add_remove_allowed_user_normalizes_types(self):
        gw, _ = make_gateway(allowed_users=[])
        gw.add_allowed_user(777)
        assert gw.is_user_allowed("777")
        assert gw.is_user_allowed(777)
        gw.remove_allowed_user("777")
        assert not gw.is_user_allowed(777)


# ---------------------------------------------------------------------------
# Start / stop lifecycle with mocked transport
# ---------------------------------------------------------------------------

class TestStartStopLifecycle:
    @pytest.mark.asyncio
    async def test_start_then_stop(self):
        gw, app = make_gateway(allowed_users=["1"])

        assert await gw.start() is True
        assert gw.is_running is True
        assert app.calls == ["initialize", "start"]
        app.updater.start_polling.assert_awaited_once()
        # Pending updates from before startup must not be replayed.
        assert app.updater.start_polling.await_args.kwargs.get("drop_pending_updates") is True

        await gw.stop()
        assert gw.is_running is False
        assert gw.app is None
        app.updater.stop.assert_awaited_once()
        assert "stop" in app.calls
        assert "shutdown" in app.calls

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        gw, app = make_gateway(allowed_users=["1"])
        builds = []
        original = gw._build_application
        gw._build_application = lambda: builds.append(1) or original()

        assert await gw.start() is True
        assert await gw.start() is True  # second start is a no-op
        assert builds == [1]
        assert app.calls.count("initialize") == 1

    @pytest.mark.asyncio
    async def test_stop_is_idempotent_and_safe_without_start(self):
        gw, _ = make_gateway(allowed_users=["1"])
        await gw.stop()  # never started: must not raise
        assert gw.is_running is False

        await gw.start()
        await gw.stop()
        await gw.stop()  # double stop must not raise
        assert gw.is_running is False

    @pytest.mark.asyncio
    async def test_start_without_token_fails(self):
        gw, _ = make_gateway(allowed_users=["1"], token=None)
        assert await gw.start() is False
        assert gw.is_running is False

    @pytest.mark.asyncio
    async def test_start_failure_cleans_up(self):
        """Network/auth failure during startup must not leave a half-started
        gateway claiming to be running."""
        failing_app = FakeApp(fail_on="initialize")
        gw, _ = make_gateway(allowed_users=["1"], app=failing_app)

        assert await gw.start() is False
        assert gw.is_running is False
        assert gw.app is None
        assert "shutdown" in failing_app.calls  # cleanup happened

    @pytest.mark.asyncio
    async def test_build_failure_returns_false(self):
        gw = TelegramGateway(bot_token=FAKE_TOKEN, allowed_users=["1"])

        def boom():
            raise ImportError("python-telegram-bot missing")

        gw._build_application = boom
        assert await gw.start() is False
        assert gw.is_running is False

    @pytest.mark.asyncio
    async def test_send_message(self):
        gw, app = make_gateway(allowed_users=["1"])

        # Not running yet: refuse to send.
        assert await gw.send_message("12345", "hi") is False

        await gw.start()
        assert await gw.send_message("12345", "hi") is True
        app.bot.send_message.assert_awaited_once()
        assert app.bot.send_message.await_args.kwargs["chat_id"] == 12345

        await gw.stop()
        assert await gw.send_message("12345", "hi") is False

    @pytest.mark.asyncio
    async def test_manager_start_all_and_stop_all(self, tmp_path):
        manager = GatewayManager(config_file=str(tmp_path / "config.json"))
        gateway = manager.add_telegram(FAKE_TOKEN, allowed_users=["1"])
        app = FakeApp()
        gateway._build_application = lambda: app

        await manager.start_all()
        assert gateway.is_running is True

        ok = await manager.send_message("telegram", "1", "ping")
        assert ok is True

        await manager.stop_all()
        assert gateway.is_running is False

    @pytest.mark.asyncio
    async def test_manager_send_to_unknown_platform(self, tmp_path):
        manager = GatewayManager(config_file=str(tmp_path / "config.json"))
        assert await manager.send_message("discord", "1", "ping") is False
