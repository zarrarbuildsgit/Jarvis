"""Action executor for the Sprint 1 JARVIS runtime."""

from __future__ import annotations

import asyncio
import platform
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, Optional

from loguru import logger

from backend.agent.action_schema import Action, ActionResult, ActionStatus, ActionType
from backend.agent.tools import FileTool, ScreenTool, TerminalTool
from backend.windows import ClipboardManager, ProcessManager, ShellRunner, WindowManager, WindowsAppManager


class ActionExecutor:
    """Executes structured actions through existing JARVIS tools.

    The executor is intentionally boring and explicit. Each action type maps to a
    dedicated method so future policy/approval layers can intercept precisely.
    """

    def __init__(
        self,
        *,
        trust_level_getter: Callable[[], int] | None = None,
        screen_control=None,
        screen_capture=None,
        vision_router=None,
        plugin_manager=None,
        status_provider: Callable[[], Dict[str, Any]] | None = None,
    ):
        self.trust_level_getter = trust_level_getter or (lambda: 1)
        self.screen_control = screen_control
        self.screen_capture = screen_capture
        self.vision_router = vision_router
        self.plugin_manager = plugin_manager
        self.status_provider = status_provider
        self.file_tool = FileTool()
        self.terminal_tool = TerminalTool(self.trust_level_getter())
        self.shell = ShellRunner()
        self.app_manager = WindowsAppManager(self.shell)
        self.window_manager = WindowManager()
        self.clipboard_manager = ClipboardManager()
        self.process_manager = ProcessManager()
        self.screen_tool = (
            ScreenTool(screen_control, screen_capture, vision_router)
            if screen_control is not None and screen_capture is not None and vision_router is not None
            else None
        )

    async def execute_plan(self, actions: Iterable[Action]) -> list[ActionResult]:
        results: list[ActionResult] = []
        for action in actions:
            result = await self.execute(action)
            results.append(result)
            if not result.success:
                break
        return results

    async def execute(self, action: Action) -> ActionResult:
        result = ActionResult(action.id, action.type, ActionStatus.RUNNING)
        if action.required_trust > self.trust_level_getter():
            return result.finish(
                ActionStatus.BLOCKED,
                f"Action requires trust level {action.required_trust}; current level is {self.trust_level_getter()}.",
            )

        try:
            handler = {
                ActionType.NOOP: self._noop,
                ActionType.RESPOND: self._respond,
                ActionType.STATUS: self._status,
                ActionType.LIST_PLUGINS: self._list_plugins,
                ActionType.RUN_TERMINAL: self._run_terminal,
                ActionType.OPEN_APP: self._open_app,
                ActionType.LIST_WINDOWS: self._list_windows,
                ActionType.FOCUS_WINDOW: self._focus_window,
                ActionType.LIST_PROCESSES: self._list_processes,
                ActionType.GET_CLIPBOARD: self._get_clipboard,
                ActionType.SET_CLIPBOARD: self._set_clipboard,
                ActionType.PASTE_CLIPBOARD: self._paste_clipboard,
                ActionType.LIST_FILES: self._list_files,
                ActionType.READ_FILE: self._read_file,
                ActionType.WRITE_FILE: self._write_file,
                ActionType.ANALYZE_SCREEN: self._analyze_screen,
                ActionType.CLICK: self._click,
                ActionType.TYPE_TEXT: self._type_text,
                ActionType.PRESS_KEY: self._press_key,
            }.get(action.type)
            if not handler:
                return result.finish(ActionStatus.FAILED, f"No executor for action type {action.type}")
            output = await asyncio.wait_for(handler(action), timeout=action.timeout_seconds)
            message = self._message_from_output(action, output)
            return result.finish(ActionStatus.SUCCESS, message=message, output=output)
        except asyncio.TimeoutError:
            return result.finish(ActionStatus.FAILED, error="Action timed out", message=f"Timed out: {action.description or action.type.value}")
        except Exception as exc:
            logger.exception("Action execution failed: %s", action.to_dict())
            return result.finish(ActionStatus.FAILED, error=str(exc), message=f"Failed: {exc}")

    async def _noop(self, action: Action) -> str:
        return action.parameters.get("message", "No action taken")

    async def _respond(self, action: Action) -> str:
        return str(action.parameters.get("message", ""))

    async def _status(self, action: Action) -> Dict[str, Any]:
        base = {
            "time": datetime.now().isoformat(),
            "platform": platform.platform(),
            "trust_level": self.trust_level_getter(),
        }
        if self.status_provider:
            try:
                base.update(self.status_provider())
            except Exception as exc:
                base["status_provider_error"] = str(exc)
        return base

    async def _list_plugins(self, action: Action) -> list[Any]:
        if not self.plugin_manager:
            return []
        if hasattr(self.plugin_manager, "describe"):
            return self.plugin_manager.describe()
        return self.plugin_manager.list_plugins()

    async def _run_terminal(self, action: Action) -> str:
        command = str(action.parameters.get("command", "")).strip()
        cwd = action.parameters.get("working_dir")
        self.terminal_tool.trust_level = self.trust_level_getter()
        return await asyncio.to_thread(self.terminal_tool.execute, command, cwd)

    async def _open_app(self, action: Action) -> str:
        target = str(action.parameters.get("target", "")).strip()
        if not target:
            raise ValueError("Missing open target")
        result = await asyncio.to_thread(self.app_manager.open_app, target)
        return result.message if result.success else f"❌ {result.message}"

    async def _list_windows(self, action: Action) -> list[dict]:
        windows = await asyncio.to_thread(self.window_manager.list_windows)
        return [w.to_dict() for w in windows[: int(action.parameters.get("limit", 50))]]

    async def _focus_window(self, action: Action) -> str:
        title = str(action.parameters.get("title", "")).strip()
        if not title:
            raise ValueError("Missing window title")
        success = await asyncio.to_thread(self.window_manager.focus_window, title)
        return f"✓ Focused window matching '{title}'" if success else f"❌ Window not found or could not focus: {title}"

    async def _list_processes(self, action: Action) -> list[dict]:
        limit = int(action.parameters.get("limit", 50))
        processes = await asyncio.to_thread(self.process_manager.list_processes, limit)
        return [p.to_dict() for p in processes]

    async def _get_clipboard(self, action: Action) -> str:
        result = await asyncio.to_thread(self.clipboard_manager.get_text)
        return result.text if result.success else f"❌ {result.message}"

    async def _set_clipboard(self, action: Action) -> str:
        text = str(action.parameters.get("text", ""))
        result = await asyncio.to_thread(self.clipboard_manager.set_text, text)
        return result.message if result.success else f"❌ {result.message}"

    async def _paste_clipboard(self, action: Action) -> str:
        if self.screen_tool:
            return await asyncio.to_thread(self.screen_tool.press_key, "v", True, False, False)
        if self.screen_control:
            success = await asyncio.to_thread(self.screen_control.press_key, "v", ["ctrl"])
            return "✓ Pasted clipboard" if success else "❌ Failed to paste clipboard"
        return "❌ Paste unavailable: screen tools are not initialized"

    async def _list_files(self, action: Action) -> str:
        directory = str(action.parameters.get("directory", "."))
        pattern = str(action.parameters.get("pattern", "*"))
        return await asyncio.to_thread(self.file_tool.list_files, directory, pattern)

    async def _read_file(self, action: Action) -> str:
        filepath = str(action.parameters.get("filepath", ""))
        max_lines = int(action.parameters.get("max_lines", 100))
        return await asyncio.to_thread(self.file_tool.read_file, filepath, max_lines)

    async def _write_file(self, action: Action) -> str:
        filepath = str(action.parameters.get("filepath", ""))
        content = str(action.parameters.get("content", ""))
        return await asyncio.to_thread(self.file_tool.write_file, filepath, content)

    async def _analyze_screen(self, action: Action) -> str:
        if not self.screen_tool:
            return "❌ Screen analysis unavailable: screen tools are not initialized"
        query = str(action.parameters.get("query", "What is on the screen?"))
        return await asyncio.to_thread(self.screen_tool.analyze_screen, query)

    async def _click(self, action: Action) -> str:
        if not self.screen_tool:
            return "❌ Click unavailable: screen tools are not initialized"
        x = int(action.parameters["x"])
        y = int(action.parameters["y"])
        button = str(action.parameters.get("button", "left"))
        return await asyncio.to_thread(self.screen_tool.click_element, x, y, button)

    async def _type_text(self, action: Action) -> str:
        if not self.screen_tool:
            return "❌ Typing unavailable: screen tools are not initialized"
        text = str(action.parameters.get("text", ""))
        return await asyncio.to_thread(self.screen_tool.type_text, text)

    async def _press_key(self, action: Action) -> str:
        if not self.screen_tool:
            return "❌ Keyboard unavailable: screen tools are not initialized"
        key = str(action.parameters.get("key", ""))
        modifiers = list(action.parameters.get("modifiers", []))
        return await asyncio.to_thread(
            self.screen_tool.press_key,
            key,
            "ctrl" in modifiers,
            "shift" in modifiers,
            "alt" in modifiers,
        )

    def _message_from_output(self, action: Action, output: Any) -> str:
        if action.type == ActionType.STATUS:
            return "JARVIS status collected"
        if action.type == ActionType.LIST_PLUGINS:
            return f"Found {len(output)} plugin(s)"
        if action.type == ActionType.LIST_WINDOWS:
            return f"Found {len(output)} window(s)"
        if action.type == ActionType.LIST_PROCESSES:
            return f"Found {len(output)} process(es)"
        if isinstance(output, str):
            return output
        return f"Completed {action.type.value}"
