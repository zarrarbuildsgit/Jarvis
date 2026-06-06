"""Typed configuration schema for JARVIS.

The schema is intentionally lightweight and dependency-free. It validates the
parts of config the runtime needs today while preserving unknown future keys.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass(slots=True)
class SystemConfig:
    name: str = "JARVIS"
    version: str = "0.1.0"
    phase: int = 5
    debug: bool = False
    profile: str = "default"


@dataclass(slots=True)
class HardwareConfig:
    gpu: str = "auto"
    max_vram_gb: float = 4.0
    max_ram_gb: float = 16.0
    threads: int = 4
    optimization_profile: str = "auto"
    lazy_load_models: bool = True


@dataclass(slots=True)
class ApiConfig:
    fastapi_host: str = "127.0.0.1"
    fastapi_port: int = 8000
    express_host: str = "127.0.0.1"
    express_port: int = 3001


@dataclass(slots=True)
class FeatureConfig:
    windows_service: bool = True
    system_tray: bool = True
    plugins: bool = True
    debate: bool = True
    continuous_conversation: bool = True
    require_approvals: bool = True


@dataclass(slots=True)
class JarvisConfig:
    system: SystemConfig = field(default_factory=SystemConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    raw: Dict[str, Any] = field(default_factory=dict)
    loaded_files: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], loaded_files: list[str] | None = None) -> "JarvisConfig":
        system_data = data.get("system", {}) or {}
        hardware_data = data.get("hardware", {}) or {}
        api_data = data.get("api", {}) or {}
        phase5_data = data.get("phase5", {}) or {}

        fastapi = api_data.get("fastapi", {}) or {}
        express = api_data.get("express", {}) or {}

        features = FeatureConfig(
            windows_service=bool((phase5_data.get("windows_service", {}) or {}).get("enabled", True)),
            system_tray=bool((phase5_data.get("system_tray", {}) or {}).get("enabled", True)),
            plugins=bool((phase5_data.get("plugins", {}) or {}).get("enabled", True)),
            debate=bool((phase5_data.get("debate", {}) or {}).get("enabled", True)),
            continuous_conversation=bool((phase5_data.get("continuous_conversation", {}) or {}).get("enabled", True)),
            require_approvals=bool((data.get("security", {}) or {}).get("require_approvals", True)),
        )

        return cls(
            system=SystemConfig(
                name=str(system_data.get("name", "JARVIS")),
                version=str(system_data.get("version", "0.1.0")),
                phase=int(system_data.get("phase", 5)),
                debug=bool(system_data.get("debug", False)),
                profile=str(system_data.get("profile", "default")),
            ),
            hardware=HardwareConfig(
                gpu=str(hardware_data.get("gpu", "auto")),
                max_vram_gb=float(hardware_data.get("max_vram_gb", 4)),
                max_ram_gb=float(hardware_data.get("max_ram_gb", 16)),
                threads=int(hardware_data.get("threads", 4)),
                optimization_profile=str(hardware_data.get("optimization_profile", "auto")),
                lazy_load_models=bool(hardware_data.get("lazy_load_models", True)),
            ),
            api=ApiConfig(
                fastapi_host=str(fastapi.get("host", "127.0.0.1")),
                fastapi_port=int(fastapi.get("port", 8000)),
                express_host=str(express.get("host", "127.0.0.1")),
                express_port=int(express.get("port", 3001)),
            ),
            features=features,
            raw=data,
            loaded_files=loaded_files or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system": asdict(self.system),
            "hardware": asdict(self.hardware),
            "api": asdict(self.api),
            "features": asdict(self.features),
            "loaded_files": list(self.loaded_files),
            "raw": self.raw,
        }

    def summary(self) -> str:
        return (
            f"profile={self.system.profile} phase={self.system.phase} "
            f"gpu={self.hardware.gpu} max_vram={self.hardware.max_vram_gb}GB "
            f"lazy_models={self.hardware.lazy_load_models} approvals={self.features.require_approvals}"
        )
