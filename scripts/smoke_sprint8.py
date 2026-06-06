"""Sprint 8 smoke checks.

Run with:
    uv run python scripts/smoke_sprint8.py

Validates that the dashboard control center files expose the expected Sprint 8
panels and backend endpoint hooks without needing to start servers.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    dashboard = Path("ui-server/public/index.html").read_text(encoding="utf-8")
    svelte = Path("frontend/src/routes/+page.svelte").read_text(encoding="utf-8")
    api = Path("backend/api.py").read_text(encoding="utf-8")
    server = Path("ui-server/src/server.mjs").read_text(encoding="utf-8")

    for token in [
        "Tasks",
        "Schedules",
        "Pending Approvals",
        "Plugins",
        "Profiles",
        "Audit Log",
        "GET /api/resources",
    ]:
        if token == "GET /api/resources":
            assert_true("/api/resources" in dashboard and "resources" in dashboard, "resources panel")
        else:
            assert_true(token in dashboard, f"dashboard contains {token}")

    for endpoint in [
        "/api/trust",
        "/api/trust/level",
        "/api/memory/stats",
        "/api/tasks/history",
        "/api/schedules",
        "/api/resources",
        "/api/config/profiles",
    ]:
        assert_true(endpoint in api or endpoint in dashboard, f"endpoint wired: {endpoint}")

    assert_true("express.static(publicDir)" in server, "ui-server serves public dashboard")
    assert_true("contentSecurityPolicy: false" in server, "helmet CSP disabled for local dashboard websocket/fetch")
    assert_true("approvals" in svelte and "schedules" in svelte and "plugins" in svelte, "Svelte dashboard source updated")

    print("✅ Sprint 8 smoke checks passed")


if __name__ == "__main__":
    main()
