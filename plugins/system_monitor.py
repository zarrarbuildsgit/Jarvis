from __future__ import annotations

import platform
import subprocess

from backend.agent.action_schema import Action, ActionType
from backend.plugins.base import PluginResult
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

        info = {"platform": platform.platform(), "python": platform.python_version()}
        lines = [f"OS: {info['platform']}", f"Python: {info['python']}"]
        try:
            import psutil
            info.update({
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_percent": psutil.virtual_memory().percent,
                "ram_available_gb": round(psutil.virtual_memory().available / (1024 ** 3), 2),
            })
            lines.extend([f"CPU: {info['cpu_percent']}%", f"RAM: {info['ram_percent']}% used ({info['ram_available_gb']} GB available)"])
        except Exception as exc:
            info["psutil_error"] = str(exc)
            lines.append("CPU/RAM: psutil unavailable")

        try:
            nvidia = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total,utilization.gpu", "--format=csv,noheader"], capture_output=True, text=True, timeout=3)
            if nvidia.returncode == 0 and nvidia.stdout.strip():
                info["gpu"] = nvidia.stdout.strip()
                lines.append("GPU: " + nvidia.stdout.strip())
            else:
                lines.append("GPU: nvidia-smi unavailable")
        except Exception:
            lines.append("GPU: nvidia-smi unavailable")

        return PluginResult(True, True, "\n".join(lines), self.name, info)
