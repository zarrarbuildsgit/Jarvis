"""Resource pressure guard for local model/runtime decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.system.gpu_monitor import GPUMonitor, SystemResources


class PressureLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(slots=True)
class ResourcePressure:
    level: PressureLevel
    reasons: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    snapshot: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_high_or_worse(self) -> bool:
        return self.level in {PressureLevel.HIGH, PressureLevel.CRITICAL}

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["level"] = self.level.value
        return data


@dataclass(slots=True)
class ResourceGuardConfig:
    profile_name: str = "default"
    max_vram_gb: float = 4.0
    max_ram_gb: float = 16.0
    ram_high_percent: float = 85.0
    ram_critical_percent: float = 93.0
    vram_high_percent: float = 82.0
    vram_critical_percent: float = 92.0
    min_free_vram_mb_for_heavy_model: float = 2500.0
    min_free_vram_mb_for_medium_model: float = 1200.0


class ResourceGuard:
    """Assesses resource pressure and makes model-loading recommendations."""

    HEAVY_MODELS = {"qwen", "qwen2.5-vl", "qwen2vl", "f5_tts"}
    MEDIUM_MODELS = {"florence2", "canary"}

    def __init__(self, config: ResourceGuardConfig | None = None, monitor: GPUMonitor | None = None):
        self.config = config or ResourceGuardConfig()
        self.monitor = monitor or GPUMonitor()

    @classmethod
    def from_jarvis_config(cls, jarvis_config) -> "ResourceGuard":
        hardware = getattr(jarvis_config, "hardware", None)
        system = getattr(jarvis_config, "system", None)
        return cls(
            ResourceGuardConfig(
                profile_name=getattr(system, "profile", "default"),
                max_vram_gb=float(getattr(hardware, "max_vram_gb", 4.0)),
                max_ram_gb=float(getattr(hardware, "max_ram_gb", 16.0)),
            )
        )

    def snapshot(self) -> SystemResources:
        return self.monitor.snapshot()

    def assess(self, snapshot: Optional[SystemResources] = None) -> ResourcePressure:
        snap = snapshot or self.snapshot()
        reasons: list[str] = []
        actions: list[str] = []
        score = 0

        if snap.ram_used_percent >= self.config.ram_critical_percent:
            score = max(score, 3)
            reasons.append(f"RAM critical: {snap.ram_used_percent:.1f}% used")
            actions.append("Pause nonessential tasks and unload idle models")
        elif snap.ram_used_percent >= self.config.ram_high_percent:
            score = max(score, 2)
            reasons.append(f"RAM high: {snap.ram_used_percent:.1f}% used")
            actions.append("Prefer lightweight models and avoid batch work")

        gpu = snap.primary_gpu
        if gpu and gpu.memory_total_mb > 0:
            if gpu.memory_used_percent >= self.config.vram_critical_percent:
                score = max(score, 3)
                reasons.append(f"VRAM critical: {gpu.memory_used_percent:.1f}% used")
                actions.append("Unload vision/TTS models before loading more")
            elif gpu.memory_used_percent >= self.config.vram_high_percent:
                score = max(score, 2)
                reasons.append(f"VRAM high: {gpu.memory_used_percent:.1f}% used")
                actions.append("Avoid heavy model loads")

            if self.config.max_vram_gb <= 4.2:
                reasons.append("4GB-class VRAM profile active")
                actions.append("Keep Qwen disabled unless explicitly overridden")
        elif self.config.max_vram_gb <= 0:
            reasons.append("CPU-only profile active")
            actions.append("Use CPU/lightweight models only")

        level = [PressureLevel.LOW, PressureLevel.MEDIUM, PressureLevel.HIGH, PressureLevel.CRITICAL][score]
        return ResourcePressure(level=level, reasons=reasons, actions=actions, snapshot=snap.to_dict())

    def can_load_model(self, model_name: str, snapshot: Optional[SystemResources] = None) -> tuple[bool, str]:
        name = model_name.lower()
        pressure = self.assess(snapshot)
        gpu = None
        if pressure.snapshot.get("gpus"):
            gpu = pressure.snapshot["gpus"][0]

        if self.config.profile_name in {"gtx1050ti", "low_ram", "safe_mode"} and name in self.HEAVY_MODELS:
            return False, f"{model_name} is disabled for profile {self.config.profile_name}"

        if pressure.level == PressureLevel.CRITICAL:
            return False, "Resource pressure is critical"

        if gpu:
            free_mb = float(gpu.get("memory_free_mb", 0.0))
            if name in self.HEAVY_MODELS and free_mb < self.config.min_free_vram_mb_for_heavy_model:
                return False, f"Not enough free VRAM for heavy model {model_name}: {free_mb:.0f} MB free"
            if name in self.MEDIUM_MODELS and free_mb < self.config.min_free_vram_mb_for_medium_model:
                return False, f"Not enough free VRAM for medium model {model_name}: {free_mb:.0f} MB free"

        return True, "Model load allowed"

    def should_unload_idle_models(self, snapshot: Optional[SystemResources] = None) -> bool:
        return self.assess(snapshot).is_high_or_worse
