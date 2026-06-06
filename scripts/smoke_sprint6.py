"""Sprint 6 smoke checks.

Run with:
    uv run python scripts/smoke_sprint6.py

Validates resource telemetry contracts, pressure decisions, model load guards,
and idle model cache behavior without requiring an NVIDIA GPU.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.optimization.model_cache import ModelCache
from backend.system.gpu_monitor import GPUInfo, SystemResources
from backend.system.resource_guard import PressureLevel, ResourceGuard, ResourceGuardConfig


class FakeMonitor:
    def __init__(self, snapshot: SystemResources):
        self._snapshot = snapshot

    def snapshot(self) -> SystemResources:
        return self._snapshot


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    low_snapshot = SystemResources(cpu_percent=10, ram_used_percent=40, ram_total_gb=16, ram_available_gb=9)
    low_snapshot.gpus = [GPUInfo(name="GTX 1050 Ti", memory_used_mb=500, memory_total_mb=4096, utilization_percent=5)]
    guard = ResourceGuard(ResourceGuardConfig(profile_name="default", max_vram_gb=6), FakeMonitor(low_snapshot))
    pressure = guard.assess()
    assert_true(pressure.level == PressureLevel.LOW, "low pressure")
    allowed, reason = guard.can_load_model("florence2")
    assert_true(allowed, f"florence2 allowed: {reason}")

    gtx_guard = ResourceGuard(ResourceGuardConfig(profile_name="gtx1050ti", max_vram_gb=4), FakeMonitor(low_snapshot))
    allowed, reason = gtx_guard.can_load_model("qwen")
    assert_true(not allowed and "gtx1050ti" in reason, "qwen blocked on gtx profile")

    high_snapshot = SystemResources(cpu_percent=80, ram_used_percent=95, ram_total_gb=16, ram_available_gb=0.8)
    high_snapshot.gpus = [GPUInfo(name="GTX 1050 Ti", memory_used_mb=3900, memory_total_mb=4096, utilization_percent=95)]
    high_guard = ResourceGuard(ResourceGuardConfig(profile_name="default", max_vram_gb=4), FakeMonitor(high_snapshot))
    high_pressure = high_guard.assess()
    assert_true(high_pressure.level == PressureLevel.CRITICAL, "critical pressure")
    allowed, reason = high_guard.can_load_model("florence2")
    assert_true(not allowed and "critical" in reason.lower(), "critical pressure blocks model")
    assert_true(high_guard.should_unload_idle_models(), "critical pressure unload recommendation")

    unloaded = []
    cache = ModelCache()
    cache.register("dummy", unload_callback=lambda: unloaded.append("dummy"))
    cache.entries["dummy"].last_used = cache.entries["dummy"].last_used.replace(year=2000)
    removed = cache.unload_idle(1)
    assert_true(removed == ["dummy"], "idle model unloaded")
    assert_true(unloaded == ["dummy"], "unload callback called")
    assert_true(cache.stats()["count"] == 0, "cache empty")

    print("✅ Sprint 6 smoke checks passed")


if __name__ == "__main__":
    main()
