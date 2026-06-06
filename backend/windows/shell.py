"""Windows-aware shell helpers with cross-platform fallbacks.

The Windows automation layer uses this module instead of sprinkling subprocess
calls throughout the codebase. Methods are deterministic, timeout-bounded, and
return structured results.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import os
import platform
import subprocess
import sys
import webbrowser


@dataclass(slots=True)
class ShellResult:
    command: list[str] | str
    success: bool
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShellRunner:
    """Small safe wrapper around OS shell operations."""

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        self.system = platform.system()

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

    def run(self, command: list[str] | str, cwd: str | None = None, shell: bool = False, timeout: Optional[int] = None) -> ShellResult:
        try:
            proc = subprocess.run(
                command,
                cwd=cwd,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout_seconds,
            )
            return ShellResult(
                command=command,
                success=proc.returncode == 0,
                returncode=proc.returncode,
                stdout=proc.stdout.strip(),
                stderr=proc.stderr.strip(),
                message="Command completed" if proc.returncode == 0 else "Command failed",
            )
        except subprocess.TimeoutExpired as exc:
            return ShellResult(command=command, success=False, returncode=-1, stdout=exc.stdout or "", stderr=exc.stderr or "", message="Command timed out")
        except Exception as exc:
            return ShellResult(command=command, success=False, returncode=-1, stderr=str(exc), message=f"Command error: {exc}")

    def open_target(self, target: str) -> ShellResult:
        """Open an app, file, folder, or URL through the OS shell."""
        target = str(target).strip()
        if not target:
            return ShellResult(command=[], success=False, returncode=-1, message="Missing target")

        if self._looks_like_url(target):
            ok = webbrowser.open(target)
            return ShellResult(command=f"webbrowser.open({target})", success=ok, message=f"Opened URL: {target}" if ok else f"Failed to open URL: {target}")

        if self.is_windows:
            try:
                os.startfile(target)  # type: ignore[attr-defined]
                return ShellResult(command=f"os.startfile({target})", success=True, message=f"Opened {target}")
            except Exception:
                # Fall back to Start-Process; useful for app aliases like notepad.
                return self.run(["powershell", "-NoProfile", "-Command", "Start-Process", target], shell=False, timeout=10)

        if self.system == "Darwin":
            return self.run(["open", target], timeout=10)

        # Linux/dev fallback. If xdg-open is unavailable, return a clear failure.
        return self.run(["xdg-open", target], timeout=10)

    def start_process(self, executable: str, args: Iterable[str] | None = None, cwd: str | None = None) -> ShellResult:
        args = list(args or [])
        command = [executable, *args]
        try:
            subprocess.Popen(command, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return ShellResult(command=command, success=True, message=f"Started {executable}")
        except Exception as exc:
            return ShellResult(command=command, success=False, returncode=-1, stderr=str(exc), message=f"Failed to start {executable}: {exc}")

    def reveal_in_file_manager(self, path: str) -> ShellResult:
        path = str(Path(path))
        if self.is_windows:
            return self.run(["explorer", "/select,", path], timeout=10)
        if self.system == "Darwin":
            return self.run(["open", "-R", path], timeout=10)
        return self.open_target(str(Path(path).parent))

    def _looks_like_url(self, target: str) -> bool:
        return target.startswith(("http://", "https://", "file://"))
