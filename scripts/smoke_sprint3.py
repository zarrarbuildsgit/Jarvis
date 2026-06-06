"""Sprint 3 smoke checks.

Run with:
    uv run python scripts/smoke_sprint3.py

Checks Windows automation abstractions in a portable way without launching apps
or requiring a Windows desktop.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.agent.action_schema import ActionType
from backend.agent.planner import DeterministicPlanner
from backend.windows.apps import WindowsAppManager
from backend.windows.processes import ProcessManager
from backend.windows.windows import WindowManager


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    app_manager = WindowsAppManager()
    assert_true(app_manager.resolve_app("notepad") == "notepad.exe", "notepad alias")
    assert_true(app_manager.resolve_app("VS Code") == "code.exe", "vscode alias")

    planner = DeterministicPlanner()
    checks = {
        "list windows": ActionType.LIST_WINDOWS,
        "focus window Chrome": ActionType.FOCUS_WINDOW,
        "list processes": ActionType.LIST_PROCESSES,
        "get clipboard": ActionType.GET_CLIPBOARD,
        "set clipboard to hello": ActionType.SET_CLIPBOARD,
        "paste clipboard": ActionType.PASTE_CLIPBOARD,
    }
    for command, expected_action in checks.items():
        plan = planner.plan(command)
        assert_true(not plan.is_empty, f"plan exists for {command}")
        assert_true(plan.actions[0].type == expected_action, f"{command} -> {expected_action.value}")

    # Portable runtime-safe calls.
    windows = WindowManager().list_windows()
    assert_true(isinstance(windows, list), "window list returns list")
    processes = ProcessManager().list_processes(limit=5)
    assert_true(isinstance(processes, list), "process list returns list")

    print("✅ Sprint 3 smoke checks passed")


if __name__ == "__main__":
    main()
