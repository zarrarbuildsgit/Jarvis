from __future__ import annotations

import re

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from plugins._safety import SafePluginMixin


class Plugin(SafePluginMixin):
    name = "file_manager"
    description = "List, read, and write files through safe deterministic file tools."
    min_trust_level = 1
    permissions = ["list_files", "read_file", "write_file"]
    examples = ["list files in .", "read file README.md", "create file notes.txt with hello"]

    def __init__(self):
        super().__init__()
        self.files = None

    def _files(self):
        if self.files is None:
            from backend.agent.tools import FileTool
            self.files = FileTool()
        return self.files

    def can_handle(self, command, context):
        c = command.lower().strip()
        return c in {"ls", "dir"} or c.startswith(("list files", "show files", "list directory", "read file", "show file", "cat ", "create file", "write file", "save file"))

    async def handle(self, command, context):
        c = command.lower().strip()
        if c in {"ls", "dir"} or c.startswith(("list files", "show files", "list directory")):
            directory = self._extract_after(command, ["list files in", "show files in", "list directory", "list files", "show files", "ls", "dir"]) or "."
            action = Action(ActionType.LIST_FILES, {"directory": directory}, required_trust=1)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            return PluginResult(True, True, self._files().list_files(directory), self.name)

        if c.startswith(("read file", "show file", "cat ")):
            path = self._extract_after(command, ["read file", "show file", "cat"])
            action = Action(ActionType.READ_FILE, {"filepath": path}, required_trust=1)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            output = self._files().read_file(path)
            return PluginResult(True, not output.startswith("❌"), output, self.name)

        match = re.match(r"(?is)^(?:create|write|save)\s+(?:file\s+)?(?P<path>.+?)\s+(?:with|containing|that says)\s+(?P<content>.+)$", command.strip())
        if match:
            path = match.group("path").strip().strip('"\'')
            content = match.group("content").strip().strip('"\'')
            action = Action(ActionType.WRITE_FILE, {"filepath": path, "content": content}, required_trust=2)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            output = self._files().write_file(path, content)
            return PluginResult(True, not output.startswith("❌"), output, self.name)

        return PluginResult(False)

    def _extract_after(self, command, prefixes):
        lower = command.lower().strip()
        for prefix in sorted(prefixes, key=len, reverse=True):
            if lower == prefix:
                return ""
            if lower.startswith(prefix + " "):
                return command.strip()[len(prefix):].strip().strip('"\'')
        return ""
