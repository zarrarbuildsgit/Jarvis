"""Browser session abstraction for deterministic local browser actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse
import re
import urllib.request
import webbrowser


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class BrowserResult:
    success: bool
    message: str
    url: str = ""
    title: str = ""
    text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BrowserSessionState:
    last_url: str = ""
    last_title: str = ""
    last_text_summary: str = ""
    opened_urls: List[str] = field(default_factory=list)
    updated_at: str = field(default_factory=now_iso)

    def remember(self, result: BrowserResult) -> None:
        if result.url:
            self.last_url = result.url
            if result.url not in self.opened_urls:
                self.opened_urls.append(result.url)
                self.opened_urls = self.opened_urls[-50:]
        if result.title:
            self.last_title = result.title
        if result.text:
            self.last_text_summary = result.text[:500]
        self.updated_at = now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BrowserSession:
    """Deterministic browser helper.

    This does not attempt unsafe remote control. It opens URLs with the OS
    default browser and can fetch readable page text for HTTP(S) URLs.
    """

    def __init__(self):
        self.state = BrowserSessionState()

    def open_url(self, url: str) -> BrowserResult:
        url = self.normalize_url(url)
        ok = webbrowser.open(url)
        result = BrowserResult(ok, f"Opened URL: {url}" if ok else f"Failed to open URL: {url}", url=url)
        self.state.remember(result)
        return result

    def search(self, query: str, engine: str = "google") -> BrowserResult:
        query = query.strip()
        if engine == "youtube":
            url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
        elif engine == "duckduckgo":
            url = "https://duckduckgo.com/?q=" + quote_plus(query)
        else:
            url = "https://www.google.com/search?q=" + quote_plus(query)
        return self.open_url(url)

    def read_url(self, url: str, max_chars: int = 5000, timeout: int = 10) -> BrowserResult:
        url = self.normalize_url(url)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return BrowserResult(False, "Only HTTP/HTTPS URLs can be read safely", url=url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/0.1 local assistant"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read(max_chars * 4)
                content_type = response.headers.get("content-type", "")
            html = raw.decode("utf-8", errors="ignore")
            title = self._extract_title(html)
            text = self._html_to_text(html)[:max_chars]
            result = BrowserResult(True, f"Read {len(text)} characters from {url}", url=url, title=title, text=text, metadata={"content_type": content_type})
            self.state.remember(result)
            return result
        except Exception as exc:
            return BrowserResult(False, f"Failed to read URL: {exc}", url=url)

    def normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        return url

    def _extract_title(self, html: str) -> str:
        match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return self._clean_text(match.group(1))[:200]

    def _html_to_text(self, html: str) -> str:
        html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
        html = re.sub(r"(?s)<[^>]+>", " ", html)
        return self._clean_text(html)

    def _clean_text(self, text: str) -> str:
        text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return re.sub(r"\s+", " ", text).strip()
