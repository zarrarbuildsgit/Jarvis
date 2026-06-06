"""Window discovery and focus helpers.

Uses pywinauto/uiautomation/win32gui when available on Windows. On non-Windows
systems it returns graceful empty results so development tests stay portable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import platform


@dataclass(slots=True)
class WindowInfo:
    title: str
    handle: Any = None
    class_name: str = ""
    process_id: int | None = None
    visible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WindowManager:
    def __init__(self):
        self.system = platform.system()

    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"

    def list_windows(self) -> List[WindowInfo]:
        if not self.is_windows:
            return []

        windows: list[WindowInfo] = []
        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            for window in desktop.windows():
                try:
                    windows.append(
                        WindowInfo(
                            title=window.window_text(),
                            handle=window.handle,
                            class_name=window.class_name(),
                            process_id=window.process_id(),
                            visible=window.is_visible(),
                        )
                    )
                except Exception:
                    continue
            return windows
        except Exception:
            pass

        try:
            import win32gui
            import win32process

            def callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        windows.append(WindowInfo(title=title, handle=hwnd, process_id=pid, visible=True))

            win32gui.EnumWindows(callback, None)
        except Exception:
            return windows
        return windows

    def find_window(self, title_contains: str) -> Optional[WindowInfo]:
        needle = title_contains.lower().strip()
        if not needle:
            return None
        for window in self.list_windows():
            if needle in window.title.lower():
                return window
        return None

    def focus_window(self, title_contains: str) -> bool:
        if not self.is_windows:
            return False
        window = self.find_window(title_contains)
        if not window:
            return False
        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            desktop.window(handle=window.handle).set_focus()
            return True
        except Exception:
            pass
        try:
            import win32gui
            import win32con

            win32gui.ShowWindow(window.handle, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(window.handle)
            return True
        except Exception:
            return False

    def active_window(self) -> Optional[WindowInfo]:
        if not self.is_windows:
            return None
        try:
            import win32gui
            import win32process

            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return WindowInfo(title=title, handle=hwnd, process_id=pid, visible=True)
        except Exception:
            return None
