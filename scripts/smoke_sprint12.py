"""Sprint 12 smoke checks.

Run with:
    uv run python scripts/smoke_sprint12.py

Validates browser URL/search/read helpers, draft-only external integrations,
plugin routing, and API source wiring without requiring a real browser launch.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import asyncio
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.browser import BrowserActions, BrowserSession, ExternalDraftStore
from backend.plugins.manager import PluginManager


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


class NoOpenSession(BrowserSession):
    def open_url(self, url: str):
        url = self.normalize_url(url)
        from backend.browser.session import BrowserResult
        result = BrowserResult(True, f"Opened URL: {url}", url=url)
        self.state.remember(result)
        return result


def main() -> None:
    session = BrowserSession()
    assert_true(session.normalize_url("example.com") == "https://example.com", "normalize url")
    text = session._html_to_text("<html><head><title>T</title><style>x</style></head><body>Hello <b>World</b></body></html>")
    assert_true("Hello World" in text, "html text extraction")

    with TemporaryDirectory() as tmp:
        actions = BrowserActions(NoOpenSession(), ExternalDraftStore(str(Path(tmp) / "drafts.json")))
        opened = actions.search("jarvis ai", engine="google")
        assert_true(opened.success and "google.com/search" in opened.url, "search url")
        draft = actions.draft_message("email", "test@example.com", "hello", "subject")
        assert_true(draft.id and draft.status == "draft", "draft created")
        assert_true(actions.drafts.list()[0].recipient == "test@example.com", "draft persisted")

    async def plugin_checks():
        manager = PluginManager(["plugins"])
        manager.discover()
        draft_result = await manager.try_handle("draft email to test@example.com saying hello there", {"trust_level": 2})
        assert_true(draft_result.handled and draft_result.success and "Draft created" in draft_result.message, "browser plugin draft")
        search_result = await manager.try_handle("search web for jarvis ai", {"trust_level": 2})
        assert_true(search_result.handled, "browser plugin search handled")

    asyncio.run(plugin_checks())

    api = Path("backend/api.py").read_text(encoding="utf-8")
    for endpoint in ["/api/browser/drafts", "/api/browser/read", "/api/browser/draft"]:
        assert_true(endpoint in api, f"api endpoint wired: {endpoint}")

    print("✅ Sprint 12 smoke checks passed")


if __name__ == "__main__":
    main()
