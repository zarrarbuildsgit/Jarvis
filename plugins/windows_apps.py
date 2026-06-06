from __future__ import annotations

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from backend.windows import WindowsAppManager, WindowManager
from plugins._safety import SafePluginMixin


class Plugin(SafePluginMixin):
    name = "windows_apps"
    description = "Open apps, list windows, and focus windows using deterministic Windows helpers."
    min_trust_level = 1
    permissions = ["open_app", "list_windows", "focus_window"]
    examples = ["open notepad", "list windows", "focus window Chrome"]

    def __init__(self):
        super().__init__()
        self.apps = WindowsAppManager()
        self.windows = WindowManager()

    def can_handle(self, command, context):
        c = command.lower().strip()
        return c in {"list windows", "show windows", "open windows"} or c.startswith(("open ", "launch ", "start ", "focus window ", "switch to window "))

    async def handle(self, command, context):
        c = command.lower().strip()
        if c in {"list windows", "show windows", "open windows"}:
            action = Action(ActionType.LIST_WINDOWS, required_trust=1)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            windows = [w.to_dict() for w in self.windows.list_windows()[:50]]
            if not windows:
                return PluginResult(True, True, "No windows found or window listing is unavailable on this platform.", self.name, {"windows": windows})
            lines = [f"- {w['title']}" for w in windows if w.get("title")]
            return PluginResult(True, True, "Open windows:\n" + "\n".join(lines), self.name, {"windows": windows})

        if c.startswith(("focus window ", "switch to window ")):
            title = command.split(" ", 2)[-1].strip()
            if c.startswith("switch to window "):
                title = command[len("switch to window "):].strip()
            action = Action(ActionType.FOCUS_WINDOW, {"title": title}, required_trust=2)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            ok = self.windows.focus_window(title)
            return PluginResult(True, ok, f"{'✓ Focused' if ok else '❌ Could not focus'} window matching: {title}", self.name)

        target = command.split(" ", 1)[1].strip() if " " in command else ""
        action = Action(ActionType.OPEN_APP, {"target": target}, required_trust=2)
        blocked = self.check_action(action, command, context)
        if blocked:
            return blocked
        result = self.apps.open_app(target)
        return PluginResult(True, result.success, result.message, self.name, result.to_dict())
