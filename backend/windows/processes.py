"""Process inspection helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List
import subprocess


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    name: str
    username: str = ""
    status: str = ""
    cpu_percent: float | None = None
    memory_mb: float | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcessManager:
    def list_processes(self, limit: int = 100) -> List[ProcessInfo]:
        try:
            import psutil

            processes: list[ProcessInfo] = []
            for proc in psutil.process_iter(["pid", "name", "username", "status", "memory_info"]):
                try:
                    info = proc.info
                    memory = info.get("memory_info")
                    processes.append(
                        ProcessInfo(
                            pid=int(info.get("pid") or 0),
                            name=str(info.get("name") or ""),
                            username=str(info.get("username") or ""),
                            status=str(info.get("status") or ""),
                            memory_mb=(memory.rss / (1024 * 1024)) if memory else None,
                        )
                    )
                except Exception:
                    continue
            return processes[:limit]
        except Exception:
            return self._list_processes_fallback(limit)

    def find_processes(self, name_contains: str, limit: int = 50) -> List[ProcessInfo]:
        needle = name_contains.lower().strip()
        return [p for p in self.list_processes(limit=500) if needle in p.name.lower()][:limit]

    def _list_processes_fallback(self, limit: int) -> List[ProcessInfo]:
        try:
            proc = subprocess.run(["ps", "-eo", "pid,comm"], capture_output=True, text=True, timeout=5)
            rows = proc.stdout.splitlines()[1:]
            output: list[ProcessInfo] = []
            for row in rows[:limit]:
                parts = row.strip().split(maxsplit=1)
                if len(parts) == 2 and parts[0].isdigit():
                    output.append(ProcessInfo(pid=int(parts[0]), name=parts[1]))
            return output
        except Exception:
            return []
