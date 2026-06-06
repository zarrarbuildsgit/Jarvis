"""Sprint 4 smoke checks.

Run with:
    uv run python scripts/smoke_sprint4.py

Validates first-party plugin discovery, metadata, routing, and safe read-only
execution paths without requiring Windows-only desktop APIs.
"""

from __future__ import annotations

from pathlib import Path
import asyncio
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.plugins.manager import PluginManager


REQUIRED = {
    "audio_control",
    "browser",
    "file_manager",
    "system_monitor",
    "terminal",
    "time",
    "windows_apps",
}


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


async def main() -> None:
    manager = PluginManager(["plugins"])
    manager.discover()
    names = set(manager.list_plugins())
    missing = REQUIRED - names
    assert_true(not missing, f"missing plugins: {sorted(missing)}")

    descriptions = manager.describe()
    for item in descriptions:
        assert_true("permissions" in item and "examples" in item, f"metadata missing for {item['name']}")

    status = await manager.try_handle("system resources", {"trust_level": 1})
    assert_true(status.handled and status.success, "system monitor handles read-only status")

    windows = await manager.try_handle("list windows", {"trust_level": 1})
    assert_true(windows.handled, "windows plugin handles list windows")

    terminal_blocked_low_trust = await manager.try_handle("run command echo hello", {"trust_level": 1})
    assert_true(not terminal_blocked_low_trust.handled, "terminal plugin skipped below min trust")

    terminal_danger = await manager.try_handle("run command rm -rf /", {"trust_level": 4})
    assert_true(terminal_danger.handled and not terminal_danger.success and "Blocked" in terminal_danger.message, "terminal dangerous command blocked")

    print("✅ Sprint 4 smoke checks passed")


if __name__ == "__main__":
    asyncio.run(main())
