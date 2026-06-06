"""Portable CPU/RAM/GPU resource monitoring for JARVIS.

The monitor is designed to work on Windows with NVIDIA GPUs, but it fails
softly on machines without `nvidia-smi`, CUDA, or psutil. This keeps smoke tests
portable while giving the runtime useful telemetry on the target PC.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import platform
import subprocess


@dataclass(slots=True)
class GPUInfo:
    index: int = 0
    name: str = "unknown"
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    utilization_percent: float = 0.0
    temperature_c: float | None = None
    source: str = "unknown"

    @property
    def memory_free_mb(self) -> float:
        return max(0.0, self.memory_total_mb - self.memory_used_mb)

    @property
    def memory_used_percent(self) -> float:
        if self.memory_total_mb <= 0:
            return 0.0
        return round((self.memory_used_mb / self.memory_total_mb) * 100, 2)

    @property
    def total_gb(self) -> float:
        return round(self.memory_total_mb / 1024, 2)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["memory_free_mb"] = self.memory_free_mb
        data["memory_used_percent"] = self.memory_used_percent
        data["total_gb"] = self.total_gb
        return data


@dataclass(slots=True)
class SystemResources:
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    platform: str = field(default_factory=platform.platform)
    cpu_percent: float = 0.0
    ram_used_percent: float = 0.0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    gpus: List[GPUInfo] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def primary_gpu(self) -> Optional[GPUInfo]:
        return self.gpus[0] if self.gpus else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "platform": self.platform,
            "cpu_percent": self.cpu_percent,
            "ram_used_percent": self.ram_used_percent,
            "ram_total_gb": self.ram_total_gb,
            "ram_available_gb": self.ram_available_gb,
            "gpus": [gpu.to_dict() for gpu in self.gpus],
            "warnings": list(self.warnings),
        }


class GPUMonitor:
    """Collects current system resources."""

    def snapshot(self) -> SystemResources:
        resources = SystemResources()
        self._fill_cpu_ram(resources)
        resources.gpus = self._query_nvidia_smi() or self._query_torch_cuda(resources)
        if not resources.gpus:
            resources.warnings.append("No GPU telemetry available")
        return resources

    def _fill_cpu_ram(self, resources: SystemResources) -> None:
        try:
            import psutil

            vm = psutil.virtual_memory()
            resources.cpu_percent = float(psutil.cpu_percent(interval=0.05))
            resources.ram_used_percent = float(vm.percent)
            resources.ram_total_gb = round(vm.total / (1024 ** 3), 2)
            resources.ram_available_gb = round(vm.available / (1024 ** 3), 2)
        except Exception as exc:
            resources.warnings.append(f"psutil unavailable: {exc}")

    def _query_nvidia_smi(self) -> List[GPUInfo]:
        query = "index,name,memory.used,memory.total,utilization.gpu,temperature.gpu"
        try:
            proc = subprocess.run(
                ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                return []
            gpus: list[GPUInfo] = []
            for line in proc.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 6:
                    continue
                gpus.append(
                    GPUInfo(
                        index=int(float(parts[0])),
                        name=parts[1],
                        memory_used_mb=float(parts[2]),
                        memory_total_mb=float(parts[3]),
                        utilization_percent=float(parts[4]),
                        temperature_c=float(parts[5]),
                        source="nvidia-smi",
                    )
                )
            return gpus
        except Exception:
            return []

    def _query_torch_cuda(self, resources: SystemResources) -> List[GPUInfo]:
        try:
            import torch

            if not torch.cuda.is_available():
                return []
            gpus: list[GPUInfo] = []
            for idx in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(idx)
                total = props.total_memory / (1024 ** 2)
                used = torch.cuda.memory_allocated(idx) / (1024 ** 2)
                gpus.append(
                    GPUInfo(
                        index=idx,
                        name=props.name,
                        memory_used_mb=round(used, 2),
                        memory_total_mb=round(total, 2),
                        utilization_percent=0.0,
                        source="torch",
                    )
                )
            return gpus
        except Exception as exc:
            resources.warnings.append(f"torch cuda telemetry unavailable: {exc}")
            return []
