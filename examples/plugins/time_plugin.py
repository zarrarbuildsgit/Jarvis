from datetime import datetime
from backend.plugins.base import PluginResult

class Plugin:
    name = "time"
    description = "Answers local time/date questions. Copy to data/plugins to enable."
    min_trust_level = 1

    def can_handle(self, command, context):
        return "time" in command.lower() or "date" in command.lower()

    async def handle(self, command, context):
        return PluginResult(True, True, f"Current local time: {datetime.now().isoformat(timespec='seconds')}", self.name)
