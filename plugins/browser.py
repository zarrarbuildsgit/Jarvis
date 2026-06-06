from __future__ import annotations

from urllib.parse import quote_plus

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from backend.windows import WindowsAppManager
from plugins._safety import SafePluginMixin


class Plugin(SafePluginMixin):
    name = "browser"
    description = "Open URLs and perform browser searches safely."
    min_trust_level = 1
    permissions = ["open_url", "web_search_browser"]
    examples = ["open url https://example.com", "search web for GTX 1050 Ti benchmarks"]

    def __init__(self):
        super().__init__()
        self.apps = WindowsAppManager()

    def can_handle(self, command, context):
        c = command.lower().strip()
        return c.startswith(("open url ", "go to ", "search web for ", "google ", "search google for ", "youtube search ")) or c.startswith(("http://", "https://"))

    async def handle(self, command, context):
        c = command.lower().strip()
        if c.startswith(("http://", "https://")):
            url = command.strip()
        elif c.startswith("open url "):
            url = command[len("open url "):].strip()
        elif c.startswith("go to "):
            url = command[len("go to "):].strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
        elif c.startswith("youtube search "):
            query = command[len("youtube search "):].strip()
            url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
        else:
            query = command
            for prefix in ["search web for", "search google for", "google"]:
                if c.startswith(prefix):
                    query = command[len(prefix):].strip()
                    break
            url = "https://www.google.com/search?q=" + quote_plus(query)

        action = Action(ActionType.OPEN_APP, {"target": url}, required_trust=2)
        blocked = self.check_action(action, command, context)
        if blocked:
            return blocked
        result = self.apps.open_url(url)
        return PluginResult(True, result.success, result.message, self.name, {"url": url, "launch": result.to_dict()})
