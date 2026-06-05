"""Observation helpers for the JARVIS action runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(slots=True)
class Observation:
    """Snapshot of what JARVIS knows before/after an action."""

    source: str
    summary: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "summary": self.summary,
            "timestamp": self.timestamp,
            "data": self.data,
            "screenshot_path": self.screenshot_path,
        }


class ObservationBuilder:
    """Builds lightweight observations without forcing heavy model loads."""

    def __init__(self, screen_capture=None, screen_control=None, vision_router=None):
        self.screen_capture = screen_capture
        self.screen_control = screen_control
        self.vision_router = vision_router

    def system_observation(self) -> Observation:
        data: Dict[str, Any] = {}
        try:
            if self.screen_capture:
                data["screen"] = self.screen_capture.get_screen_info()
        except Exception as exc:  # pragma: no cover - hardware dependent
            data["screen_error"] = str(exc)
        try:
            if self.screen_control:
                data["windows"] = self.screen_control.get_all_windows()[:20]
        except Exception as exc:  # pragma: no cover - Windows dependent
            data["windows_error"] = str(exc)
        return Observation(source="system", summary="Current system/window observation", data=data)

    def screen_observation(self, query: str = "What is on the screen?") -> Observation:
        if not self.screen_capture or not self.vision_router:
            return Observation(source="screen", summary="Screen observation unavailable")
        screenshot = self.screen_capture.capture()
        if screenshot is None:
            return Observation(source="screen", summary="Could not capture screen")
        result = self.vision_router.route_query(query, screenshot)
        path = None
        try:
            path = self.screen_capture.save_screenshot()
        except Exception:
            path = None
        return Observation(
            source="screen",
            summary=str(result.get("result", "No screen result")),
            data=result,
            screenshot_path=path,
        )
