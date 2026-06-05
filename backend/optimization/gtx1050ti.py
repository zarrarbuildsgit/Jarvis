"""GTX 1050 Ti / 4GB VRAM optimization profile."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict
import os


@dataclass
class GTX1050TiProfile:
    max_vram_gb: float = 3.6
    torch_dtype: str = "float16"
    load_in_8bit: bool = True
    low_cpu_mem_usage: bool = True
    max_new_tokens_vision: int = 256
    prefer_models: tuple[str, ...] = ("smolvlm", "florence2")
    avoid_models: tuple[str, ...] = ("qwen",)
    cuda_alloc_conf: str = "max_split_size_mb:64,garbage_collection_threshold:0.8"

    def apply_environment(self) -> None:
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", self.cuda_alloc_conf)
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    def model_kwargs(self, device: str) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"low_cpu_mem_usage": self.low_cpu_mem_usage}
        if device == "cuda" and self.load_in_8bit:
            kwargs["load_in_8bit"] = True
            kwargs["device_map"] = "auto"
        return kwargs

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_profile() -> GTX1050TiProfile | None:
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            name = props.name.lower()
            vram = props.total_memory / (1024 ** 3)
            if "1050 ti" in name or vram <= 4.2:
                profile = GTX1050TiProfile()
                profile.apply_environment()
                return profile
    except Exception:
        return None
    return None
