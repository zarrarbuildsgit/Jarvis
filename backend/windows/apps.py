"""Windows app launching helpers."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from backend.windows.shell import ShellResult, ShellRunner


@dataclass(slots=True)
class AppLaunchResult:
    target: str
    resolved_target: str
    success: bool
    message: str
    shell_result: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WindowsAppManager:
    """Resolve friendly app names and launch them via the OS shell."""

    APP_ALIASES = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "command prompt": "cmd.exe",
        "powershell": "powershell.exe",
        "terminal": "wt.exe",
        "windows terminal": "wt.exe",
        "task manager": "taskmgr.exe",
        "control panel": "control.exe",
        "settings": "ms-settings:",
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe",
        "brave": "brave.exe",
        "vscode": "code.exe",
        "vs code": "code.exe",
        "visual studio code": "code.exe",
    }

    def __init__(self, shell: ShellRunner | None = None):
        self.shell = shell or ShellRunner()

    def resolve_app(self, target: str) -> str:
        clean = " ".join(str(target).strip().lower().split())
        return self.APP_ALIASES.get(clean, str(target).strip())

    def open_app(self, target: str) -> AppLaunchResult:
        resolved = self.resolve_app(target)
        shell_result = self.shell.open_target(resolved)
        return AppLaunchResult(
            target=target,
            resolved_target=resolved,
            success=shell_result.success,
            message=shell_result.message or (f"Opened {target}" if shell_result.success else f"Failed to open {target}"),
            shell_result=shell_result.to_dict(),
        )

    def open_url(self, url: str) -> AppLaunchResult:
        shell_result = self.shell.open_target(url)
        return AppLaunchResult(url, url, shell_result.success, shell_result.message, shell_result.to_dict())
