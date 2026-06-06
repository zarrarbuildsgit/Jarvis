from __future__ import annotations

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from plugins._safety import SafePluginMixin


class Plugin(SafePluginMixin):
    name = "terminal"
    description = "Run terminal commands after policy checks."
    min_trust_level = 2
    permissions = ["run_terminal"]
    examples = ["run command echo hello", "terminal git status"]

    def __init__(self):
        super().__init__()

    def can_handle(self, command, context):
        c = command.lower().strip()
        return c.startswith(("run command ", "execute command ", "terminal ", "cmd ", "powershell "))

    async def handle(self, command, context):
        cmd = self._extract(command)
        action = Action(ActionType.RUN_TERMINAL, {"command": cmd}, required_trust=2)
        blocked = self.check_action(action, command, context)
        if blocked:
            return blocked
        from backend.agent.tools import TerminalTool
        tool = TerminalTool(int(context.get("trust_level", 1)))
        output = tool.execute(cmd)
        return PluginResult(True, not output.startswith("❌"), output, self.name)

    def _extract(self, command):
        lower = command.lower().strip()
        for prefix in ["execute command", "run command", "powershell", "terminal", "cmd"]:
            if lower.startswith(prefix + " "):
                return command.strip()[len(prefix):].strip()
        return command.strip()
