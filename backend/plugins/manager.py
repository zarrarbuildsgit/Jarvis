"""Dynamic plugin discovery and execution for JARVIS."""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from typing import Any, Dict, Iterable
from loguru import logger

from backend.plugins.base import PluginResult


class PluginManager:
    def __init__(self, plugin_dirs: Iterable[str] | None = None):
        self.plugin_dirs = [Path(p) for p in (plugin_dirs or ["plugins", "data/plugins"])]
        self.plugins: Dict[str, Any] = {}

    def discover(self) -> None:
        for directory in self.plugin_dirs:
            directory.mkdir(parents=True, exist_ok=True)
            for path in directory.glob("*.py"):
                if path.name.startswith("_"):
                    continue
                self.load_plugin(path)

    def load_plugin(self, path: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{path.stem}", path)
            if not spec or not spec.loader:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin_obj = None
            if hasattr(module, "plugin"):
                plugin_obj = module.plugin
            elif hasattr(module, "Plugin"):
                plugin_obj = module.Plugin()
            else:
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if all(hasattr(obj, attr) for attr in ("can_handle", "handle", "name")):
                        plugin_obj = obj()
                        break
            if not plugin_obj:
                logger.warning("No plugin object found in %s", path)
                return False
            self.plugins[plugin_obj.name] = plugin_obj
            logger.info("Loaded plugin: %s", plugin_obj.name)
            return True
        except Exception as exc:
            logger.exception("Failed to load plugin %s: %s", path, exc)
            return False

    async def try_handle(self, command: str, context: Dict[str, Any] | None = None) -> PluginResult:
        context = context or {}
        for name, plugin in list(self.plugins.items()):
            try:
                if getattr(plugin, "min_trust_level", 1) > context.get("trust_level", 1):
                    continue
                if plugin.can_handle(command, context):
                    result = await plugin.handle(command, context)
                    result.plugin_name = result.plugin_name or name
                    return result
            except Exception as exc:
                logger.exception("Plugin %s failed", name)
                return PluginResult(True, False, f"❌ Plugin {name} failed: {exc}", name)
        return PluginResult(False)

    def list_plugins(self) -> list[str]:
        return sorted(self.plugins)

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "description": getattr(plugin, "description", ""),
                "min_trust_level": getattr(plugin, "min_trust_level", 1),
            }
            for name, plugin in sorted(self.plugins.items())
        ]
