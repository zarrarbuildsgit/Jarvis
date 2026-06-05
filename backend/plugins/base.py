"""Base classes for JARVIS plugins."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass
class PluginResult:
    handled: bool
    success: bool = False
    message: str = ""
    plugin_name: str | None = None
    data: Dict[str, Any] | None = None


class JarvisPlugin(Protocol):
    name: str
    description: str
    min_trust_level: int

    def can_handle(self, command: str, context: Dict[str, Any]) -> bool: ...
    async def handle(self, command: str, context: Dict[str, Any]) -> PluginResult: ...
