"""Profile-aware configuration loader for JARVIS."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable
import os

try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise RuntimeError("PyYAML is required for JARVIS configuration loading") from exc

from backend.config.schema import JarvisConfig


DEFAULT_CONFIG_FILE = Path("backend/config/settings.yaml")
DEFAULT_PROFILE_DIR = Path("configs")


class ConfigError(RuntimeError):
    pass


class ConfigLoader:
    def __init__(self, base_file: str | Path = DEFAULT_CONFIG_FILE, profile_dir: str | Path = DEFAULT_PROFILE_DIR):
        self.base_file = Path(base_file)
        self.profile_dir = Path(profile_dir)

    def load(self, profile: str | None = None, extra_files: Iterable[str | Path] | None = None) -> JarvisConfig:
        selected_profile = profile or os.getenv("JARVIS_PROFILE") or "default"
        loaded_files: list[str] = []
        data: Dict[str, Any] = {}

        if self.base_file.exists():
            data = self._merge(data, self._read_yaml(self.base_file))
            loaded_files.append(str(self.base_file))

        profile_file = self.profile_dir / f"{selected_profile}.yaml"
        if selected_profile != "settings" and profile_file.exists():
            data = self._merge(data, self._read_yaml(profile_file))
            loaded_files.append(str(profile_file))
        elif selected_profile not in {"default", "settings"}:
            raise ConfigError(f"Profile not found: {selected_profile} ({profile_file})")

        for extra in extra_files or []:
            path = Path(extra)
            if not path.exists():
                raise ConfigError(f"Extra config file not found: {path}")
            data = self._merge(data, self._read_yaml(path))
            loaded_files.append(str(path))

        data.setdefault("system", {})["profile"] = selected_profile
        return JarvisConfig.from_dict(data, loaded_files=loaded_files)

    def available_profiles(self) -> list[str]:
        profiles = ["default"]
        if self.profile_dir.exists():
            profiles.extend(sorted(p.stem for p in self.profile_dir.glob("*.yaml") if p.stem != "default"))
        return sorted(set(profiles))

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        try:
            content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(content, dict):
                raise ConfigError(f"Config file must contain a mapping: {path}")
            return content
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"Failed to read config file {path}: {exc}") from exc

    def _merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._merge(result[key], value)
            elif self._is_named_mapping_list(result.get(key)) and self._is_named_mapping_list(value):
                result[key] = self._merge_named_lists(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    def _is_named_mapping_list(self, value: Any) -> bool:
        return isinstance(value, list) and all(isinstance(item, dict) and "name" in item for item in value)

    def _merge_named_lists(self, base: list[dict[str, Any]], override: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {str(item["name"]): deepcopy(item) for item in base}
        order = [str(item["name"]) for item in base]
        for item in override:
            name = str(item["name"])
            if name in merged:
                merged[name] = self._merge(merged[name], item)
            else:
                merged[name] = deepcopy(item)
                order.append(name)
        return [merged[name] for name in order]


_default_loader = ConfigLoader()
_cached_config: JarvisConfig | None = None


def load_config(profile: str | None = None, *, force_reload: bool = False) -> JarvisConfig:
    global _cached_config
    if force_reload or _cached_config is None or profile is not None:
        _cached_config = _default_loader.load(profile)
    return _cached_config


def available_profiles() -> list[str]:
    return _default_loader.available_profiles()
