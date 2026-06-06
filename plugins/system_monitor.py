from __future__ import annotations

import platform

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
from backend.system.resource_guard import ResourceGuard
from backend.windows import ProcessManager
from plugins._safety import SafePluginMixin


class Plugin(SafePluginMixin):
    name = "system_monitor"
    description = "Report CPU, RAM, GPU, OS, and process information."
    min_trust_level = 1
    permissions = ["system_info", "process_list"]
    examples = ["system resources", "list processes", "gpu status"]

    def __init__(self):
        super().__init__()
        self.processes = ProcessManager()
        self.guard = ResourceGuard()

    def can_handle(self, command, context):
        c = command.lower().strip()
        return c in {"system resources", "resource status", "system monitor", "gpu status", "cpu status", "ram status", "list processes", "show processes"}

    async def handle(self, command, context):
        c = command.lower().strip()
        if "process" in c:
            action = Action(ActionType.LIST_PROCESSES, {"limit": 25}, required_trust=1)
            blocked = self.check_action(action, command, context)
            if blocked:
                return blocked
            processes = self.processes.list_processes(25)
            lines = [f"{p.pid}: {p.name} {f'({p.memory_mb:.1f} MB)' if p.memory_mb else ''}" for p in processes]
            return PluginResult(True, True, "Processes:\n" + "\n".join(lines), self.name, {"processes": [p.to_dict() for p in processes]})

        snapshot = self.guard.snapshot()
        pressure = self.guard.assess(snapshot)
        info = snapshot.to_dict()
        info["pressure"] = pressure.to_dict()
        lines = [
            f"OS: {snapshot.platform}",
            f"Python: {platform.python_version()}",
            f"CPU: {snapshot.cpu_percent}%",
            f"RAM: {snapshot.ram_used_percent}% used ({snapshot.ram_available_gb} GB available)",
            f"Pressure: {pressure.level.value}",
        ]
        if snapshot.gpus:
            for gpu in snapshot.gpus:
                lines.append(
                    f"GPU {gpu.index}: {gpu.name} — {gpu.memory_used_mb:.0f}/{gpu.memory_total_mb:.0f} MB "
                    f"({gpu.memory_used_percent:.1f}%) util={gpu.utilization_percent:.0f}%"
                )
        else:
            lines.append("GPU: telemetry unavailable")
        if pressure.reasons:
            lines.append("Reasons: " + "; ".join(pressure.reasons))
        if pressure.actions:
            lines.append("Recommended: " + "; ".join(pressure.actions))
        return PluginResult(True, True, "\n".join(lines), self.name, info)
