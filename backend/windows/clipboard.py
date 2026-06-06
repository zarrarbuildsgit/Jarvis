"""Clipboard helpers with optional pyperclip and tkinter fallbacks."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass(slots=True)
class ClipboardResult:
    success: bool
    message: str
    text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ClipboardManager:
    def get_text(self) -> ClipboardResult:
        try:
            import pyperclip

            return ClipboardResult(True, "Clipboard text read", pyperclip.paste())
        except Exception:
            pass
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            return ClipboardResult(True, "Clipboard text read", text)
        except Exception as exc:
            return ClipboardResult(False, f"Failed to read clipboard: {exc}")

    def set_text(self, text: str) -> ClipboardResult:
        text = str(text)
        try:
            import pyperclip

            pyperclip.copy(text)
            return ClipboardResult(True, "Clipboard text set", text)
        except Exception:
            pass
        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
            root.destroy()
            return ClipboardResult(True, "Clipboard text set", text)
        except Exception as exc:
            return ClipboardResult(False, f"Failed to set clipboard: {exc}", text)
