"""Sprint 5 smoke checks.

Run with:
    uv run python scripts/smoke_sprint5.py

Validates profile discovery, merging, typed schema conversion, and profile-specific
settings without importing heavyweight runtime subsystems.
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config.loader import ConfigLoader


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    loader = ConfigLoader()
    profiles = loader.available_profiles()
    for name in ["default", "gtx1050ti", "low_ram", "high_end_gpu", "safe_mode"]:
        assert_true(name in profiles, f"profile exists: {name}")

    default = loader.load("default")
    assert_true(default.system.profile == "default", "default profile name")
    assert_true(default.system.phase == 5, "default phase")
    assert_true(default.features.plugins is True, "plugins enabled")

    gtx = loader.load("gtx1050ti")
    assert_true(gtx.hardware.optimization_profile == "gtx1050ti", "gtx optimization profile")
    assert_true(gtx.hardware.max_vram_gb == 4, "gtx max vram")
    assert_true(gtx.hardware.lazy_load_models is True, "gtx lazy load")
    qwen = [m for m in gtx.raw.get("vision", {}).get("models", []) if m.get("name") == "qwen"]
    assert_true(qwen and qwen[0].get("enabled") is False, "qwen disabled on gtx")
    assert_true("id" in qwen[0], "profile merge preserves model ids")

    low = loader.load("low_ram")
    assert_true(low.hardware.gpu == "cpu", "low ram cpu mode")
    assert_true(low.hardware.threads == 2, "low ram threads")

    high = loader.load("high_end_gpu")
    assert_true(high.hardware.max_vram_gb >= 12, "high-end vram")
    qwen_high = [m for m in high.raw.get("vision", {}).get("models", []) if m.get("name") == "qwen"]
    assert_true(qwen_high and qwen_high[0].get("enabled") is True, "qwen enabled high-end")

    safe = loader.load("safe_mode")
    assert_true(safe.system.debug is True, "safe mode debug")
    assert_true(safe.features.continuous_conversation is False, "safe mode disables continuous conversation")

    print("✅ Sprint 5 smoke checks passed")


if __name__ == "__main__":
    main()
