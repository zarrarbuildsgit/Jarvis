"""Windows automation layer for JARVIS."""

from backend.windows.apps import AppLaunchResult, WindowsAppManager
from backend.windows.clipboard import ClipboardManager, ClipboardResult
from backend.windows.processes import ProcessInfo, ProcessManager
from backend.windows.shell import ShellResult, ShellRunner
from backend.windows.windows import WindowInfo, WindowManager

__all__ = [
    "AppLaunchResult",
    "ClipboardManager",
    "ClipboardResult",
    "ProcessInfo",
    "ProcessManager",
    "ShellResult",
    "ShellRunner",
    "WindowInfo",
    "WindowManager",
    "WindowsAppManager",
]
