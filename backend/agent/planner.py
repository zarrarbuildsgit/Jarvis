"""Deterministic command planner for Sprint 1.

This planner intentionally handles common low/medium complexity commands without
LLM calls. Complex commands can still fall through to CrewAI/future AI planners.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Optional

from backend.agent.action_schema import Action, ActionPlan, ActionType


class DeterministicPlanner:
    """Rule-based planner for common JARVIS commands.

    It should be conservative: only return a plan when it is confident enough.
    Returning an empty plan lets the higher-level agent use CrewAI/LLM fallback.
    """

    def plan(self, command: str) -> ActionPlan:
        original = command.strip()
        normalized = self._normalize(original)
        if not normalized:
            return ActionPlan(command=command, summary="Empty command", confidence=1.0)

        for builder in (
            self._plan_status,
            self._plan_plugins,
            self._plan_screen,
            self._plan_files,
            self._plan_terminal,
            self._plan_windows,
            self._plan_clipboard,
            self._plan_processes,
            self._plan_open_app,
            self._plan_keyboard_mouse,
        ):
            plan = builder(original, normalized)
            if plan and not plan.is_empty:
                return plan

        return ActionPlan(command=command, summary="No deterministic plan matched", confidence=0.0)

    def _normalize(self, command: str) -> str:
        return " ".join(command.lower().strip().split())

    def _plan_status(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if normalized in {"status", "/status", "jarvis status", "system status"}:
            return ActionPlan(
                command=original,
                summary="Show JARVIS runtime status",
                confidence=0.98,
                actions=[Action(ActionType.STATUS, description="Collect JARVIS status", required_trust=1)],
            )
        return None

    def _plan_plugins(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if "plugin" in normalized and any(k in normalized for k in ["list", "show", "installed", "available"]):
            return ActionPlan(
                command=original,
                summary="List installed plugins",
                confidence=0.95,
                actions=[Action(ActionType.LIST_PLUGINS, description="List plugins", required_trust=1)],
            )
        return None

    def _plan_screen(self, original: str, normalized: str) -> Optional[ActionPlan]:
        screen_phrases = [
            "what is on my screen",
            "what's on my screen",
            "describe my screen",
            "analyze screen",
            "analyze my screen",
            "read my screen",
        ]
        if any(p in normalized for p in screen_phrases):
            query = original
            return ActionPlan(
                command=original,
                summary="Analyze current screen",
                confidence=0.9,
                actions=[Action(ActionType.ANALYZE_SCREEN, {"query": query}, "Analyze screen", required_trust=1)],
            )
        return None

    def _plan_files(self, original: str, normalized: str) -> Optional[ActionPlan]:
        # list files in C:\Users\... / list directory .
        if normalized.startswith(("list files", "show files", "list directory", "show directory", "ls ", "dir ")) or normalized in {"ls", "dir"}:
            target = self._extract_after(original, ["list files in", "show files in", "list directory", "show directory", "ls", "dir"])
            directory = self._clean_path(target or ".")
            return ActionPlan(
                command=original,
                summary=f"List files in {directory}",
                confidence=0.9,
                actions=[Action(ActionType.LIST_FILES, {"directory": directory}, f"List {directory}", required_trust=1)],
            )

        if normalized.startswith(("read file", "open file", "show file", "cat ", "type file")):
            target = self._extract_after(original, ["read file", "open file", "show file", "type file", "cat"])
            if target:
                filepath = self._clean_path(target)
                return ActionPlan(
                    command=original,
                    summary=f"Read file {filepath}",
                    confidence=0.88,
                    actions=[Action(ActionType.READ_FILE, {"filepath": filepath}, f"Read {filepath}", required_trust=1)],
                )

        write_match = re.match(r"(?is)^(?:create|write|save)\s+(?:a\s+)?(?:file\s+)?(?P<path>.+?)\s+(?:with|containing|that says)\s+(?P<content>.+)$", original.strip())
        if write_match:
            filepath = self._clean_path(write_match.group("path"))
            content = self._strip_quotes(write_match.group("content"))
            return ActionPlan(
                command=original,
                summary=f"Write file {filepath}",
                confidence=0.86,
                actions=[Action(ActionType.WRITE_FILE, {"filepath": filepath, "content": content}, f"Write {filepath}", required_trust=2)],
            )
        return None

    def _plan_terminal(self, original: str, normalized: str) -> Optional[ActionPlan]:
        prefixes = ["run command", "execute command", "terminal", "cmd", "powershell"]
        if any(normalized.startswith(p) for p in prefixes):
            cmd = self._extract_after(original, prefixes)
            if cmd:
                return ActionPlan(
                    command=original,
                    summary=f"Run terminal command: {cmd}",
                    confidence=0.82,
                    actions=[Action(ActionType.RUN_TERMINAL, {"command": cmd}, f"Run {cmd}", required_trust=2)],
                )
        return None

    def _plan_windows(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if normalized in {"list windows", "show windows", "open windows", "active windows"}:
            return ActionPlan(
                command=original,
                summary="List open windows",
                confidence=0.92,
                actions=[Action(ActionType.LIST_WINDOWS, description="List open windows", required_trust=1)],
            )
        if normalized.startswith(("focus window ", "switch to window ", "activate window ")):
            title = self._extract_after(original, ["focus window", "switch to window", "activate window"])
            if title:
                return ActionPlan(
                    command=original,
                    summary=f"Focus window {title}",
                    confidence=0.88,
                    actions=[Action(ActionType.FOCUS_WINDOW, {"title": self._strip_quotes(title)}, "Focus window", required_trust=2)],
                )
        return None

    def _plan_clipboard(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if normalized in {"get clipboard", "read clipboard", "show clipboard"}:
            return ActionPlan(
                command=original,
                summary="Read clipboard text",
                confidence=0.92,
                actions=[Action(ActionType.GET_CLIPBOARD, description="Read clipboard", required_trust=1)],
            )
        if normalized.startswith(("set clipboard to ", "copy to clipboard ")):
            text = self._extract_after(original, ["set clipboard to", "copy to clipboard"])
            if text:
                return ActionPlan(
                    command=original,
                    summary="Set clipboard text",
                    confidence=0.9,
                    actions=[Action(ActionType.SET_CLIPBOARD, {"text": self._strip_quotes(text)}, "Set clipboard", required_trust=2)],
                )
        if normalized in {"paste clipboard", "paste", "paste text"}:
            return ActionPlan(
                command=original,
                summary="Paste clipboard",
                confidence=0.88,
                actions=[Action(ActionType.PASTE_CLIPBOARD, description="Paste clipboard", required_trust=2)],
            )
        return None

    def _plan_processes(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if normalized in {"list processes", "show processes", "running processes", "list running processes"}:
            return ActionPlan(
                command=original,
                summary="List running processes",
                confidence=0.9,
                actions=[Action(ActionType.LIST_PROCESSES, {"limit": 50}, "List processes", required_trust=1)],
            )
        return None

    def _plan_open_app(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if normalized.startswith(("open ", "launch ", "start ")):
            target = self._extract_after(original, ["open", "launch", "start"])
            if not target:
                return None
            target_clean = self._strip_quotes(target)
            if self._looks_like_file_command_target(target_clean):
                return None
            action_type = ActionType.OPEN_APP
            params = {"target": target_clean}
            return ActionPlan(
                command=original,
                summary=f"Open {target_clean}",
                confidence=0.84,
                actions=[Action(action_type, params, f"Open {target_clean}", required_trust=2)],
            )
        return None

    def _plan_keyboard_mouse(self, original: str, normalized: str) -> Optional[ActionPlan]:
        if normalized.startswith(("type ", "write text ")):
            text = self._extract_after(original, ["type", "write text"])
            if text:
                text = self._strip_quotes(text)
                return ActionPlan(
                    command=original,
                    summary="Type text",
                    confidence=0.9,
                    actions=[Action(ActionType.TYPE_TEXT, {"text": text}, "Type text", required_trust=2)],
                )

        if normalized.startswith(("press ", "hotkey ")):
            key_text = self._extract_after(original, ["press", "hotkey"])
            if key_text:
                key, modifiers = self._parse_key_combo(key_text)
                return ActionPlan(
                    command=original,
                    summary=f"Press {'+'.join(modifiers + [key])}",
                    confidence=0.88,
                    actions=[Action(ActionType.PRESS_KEY, {"key": key, "modifiers": modifiers}, "Press key", required_trust=2)],
                )

        click_match = re.search(r"click(?:\s+at)?\s+(?P<x>\d{1,5})\s*[, ]\s*(?P<y>\d{1,5})", normalized)
        if click_match:
            x = int(click_match.group("x"))
            y = int(click_match.group("y"))
            return ActionPlan(
                command=original,
                summary=f"Click at ({x}, {y})",
                confidence=0.92,
                actions=[Action(ActionType.CLICK, {"x": x, "y": y, "button": "left"}, f"Click at ({x}, {y})", required_trust=2)],
            )
        return None

    def _extract_after(self, original: str, prefixes: list[str]) -> str:
        lower = original.lower().strip()
        for prefix in sorted(prefixes, key=len, reverse=True):
            p = prefix.lower()
            if lower == p:
                return ""
            if lower.startswith(p + " "):
                return original.strip()[len(prefix):].strip()
        return ""

    def _clean_path(self, value: str) -> str:
        value = self._strip_quotes(value.strip())
        # Do not resolve because commands target the user's Windows machine, not this sandbox.
        return value or "."

    def _strip_quotes(self, value: str) -> str:
        value = value.strip()
        try:
            parts = shlex.split(value, posix=False)
            if len(parts) == 1:
                value = parts[0]
        except Exception:
            pass
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            return value[1:-1]
        return value

    def _looks_like_file_command_target(self, value: str) -> bool:
        suffixes = {".txt", ".md", ".py", ".json", ".yaml", ".yml", ".csv", ".log"}
        try:
            return Path(value).suffix.lower() in suffixes
        except Exception:
            return False

    def _parse_key_combo(self, key_text: str) -> tuple[str, list[str]]:
        cleaned = key_text.lower().replace(" plus ", "+").replace("-", "+")
        parts = [p.strip() for p in re.split(r"\+|,|\s+and\s+", cleaned) if p.strip()]
        aliases = {"control": "ctrl", "cmd": "win", "command": "win", "escape": "esc", "return": "enter"}
        modifiers: list[str] = []
        key = parts[-1] if parts else cleaned
        for part in parts:
            part = aliases.get(part, part)
            if part in {"ctrl", "shift", "alt", "win"}:
                modifiers.append(part)
            else:
                key = part
        return aliases.get(key, key), modifiers
