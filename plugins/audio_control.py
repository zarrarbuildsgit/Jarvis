from __future__ import annotations

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from plugins._safety import SafePluginMixin


class Plugin(SafePluginMixin):
    name = "audio_control"
    description = "Control system volume using media keys where supported."
    min_trust_level = 2
    permissions = ["press_media_keys"]
    examples = ["volume up", "volume down", "mute volume"]

    KEY_MAP = {
        "volume up": "volumeup",
        "increase volume": "volumeup",
        "turn volume up": "volumeup",
        "volume down": "volumedown",
        "decrease volume": "volumedown",
        "turn volume down": "volumedown",
        "mute": "volumemute",
        "mute volume": "volumemute",
        "unmute": "volumemute",
        "unmute volume": "volumemute",
    }

    def __init__(self):
        super().__init__()

    def can_handle(self, command, context):
        return command.lower().strip() in self.KEY_MAP

    async def handle(self, command, context):
        key = self.KEY_MAP[command.lower().strip()]
        action = Action(ActionType.PRESS_KEY, {"key": key}, required_trust=2)
        blocked = self.check_action(action, command, context)
        if blocked:
            return blocked
        try:
            import pydirectinput
            pydirectinput.press(key)
            return PluginResult(True, True, f"✓ Sent media key: {key}", self.name)
        except Exception:
            try:
                import pyautogui
                pyautogui.press(key)
                return PluginResult(True, True, f"✓ Sent media key: {key}", self.name)
            except Exception as exc:
                return PluginResult(True, False, f"❌ Audio control unavailable: {exc}", self.name)
