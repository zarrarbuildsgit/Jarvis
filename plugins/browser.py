from __future__ import annotations

import re

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from backend.browser import BrowserActions
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
        self.browser = BrowserActions()

    def can_handle(self, command, context):
        c = command.lower().strip()
        return c.startswith(("open url ", "go to ", "search web for ", "google ", "search google for ", "youtube search ", "read url ", "summarize url ", "draft email ", "draft message ")) or c.startswith(("http://", "https://"))

    async def handle(self, command, context):
        c = command.lower().strip()
        if c.startswith(("draft email ", "draft message ")):
            return await self._draft_external(command, context)

        if c.startswith(("read url ", "summarize url ")):
            url = command.split(" ", 2)[-1].strip()
            action = Action(ActionType.READ_FILE, {"url": url}, required_trust=1, description="Read/summarize URL")
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            result = self.browser.read_and_summarize(url)
            message = result.metadata.get("summary", result.message) if result.success else f"❌ {result.message}"
            return PluginResult(True, result.success, message, self.name, result.to_dict())

        if c.startswith(("http://", "https://")):
            url = command.strip()
        elif c.startswith("open url "):
            url = command[len("open url "):].strip()
        elif c.startswith("go to "):
            url = command[len("go to "):].strip()
        elif c.startswith("youtube search "):
            query = command[len("youtube search "):].strip()
            action = Action(ActionType.OPEN_APP, {"target": query}, required_trust=2)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            result = self.browser.search(query, engine="youtube")
            return PluginResult(True, result.success, result.message, self.name, result.to_dict())
        else:
            query = command
            for prefix in ["search web for", "search google for", "google"]:
                if c.startswith(prefix):
                    query = command[len(prefix):].strip()
                    break
            action = Action(ActionType.OPEN_APP, {"target": query}, required_trust=2)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            result = self.browser.search(query, engine="google")
            return PluginResult(True, result.success, result.message, self.name, result.to_dict())

        action = Action(ActionType.OPEN_APP, {"target": url}, required_trust=2)
        blocked = self.check_action(action, command, context)
        if blocked:
            return blocked
        result = self.browser.open_url(url)
        return PluginResult(True, result.success, result.message, self.name, result.to_dict())

    async def _draft_external(self, command, context):
        # Draft-only parser: "draft email to bob@example.com saying hello".
        match = re.search(r"draft (email|message)(?: to)? ([^ ]+)(?: about ([^:]+))? (?:saying|with|body) (.+)", command, flags=re.IGNORECASE)
        if not match:
            return PluginResult(True, False, "❌ Could not parse draft. Try: draft email to user@example.com saying hello", self.name)
        kind, recipient, subject, body = match.group(1), match.group(2), match.group(3) or "", match.group(4)
        # Sending is intentionally not performed. Drafting still gets audited via policy helper.
        action = Action(ActionType.WRITE_FILE, {"recipient": recipient, "subject": subject, "body": body}, required_trust=2, description=f"Draft external {kind}")
        blocked = self.check_action(action, command, context)
        if blocked:
            return blocked
        draft = self.browser.draft_message(kind, recipient, body, subject)
        return PluginResult(True, True, f"Draft created ({draft.id}). Review/approve before sending externally.", self.name, {"draft": draft.to_dict()})
