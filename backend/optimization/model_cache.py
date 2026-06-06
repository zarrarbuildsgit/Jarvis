"""Small model lifecycle registry for idle unload decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import gc


@dataclass(slots=True)
class ModelCacheEntry:
    name: str
    model: Any = None
    unload_callback: Optional[Callable[[], None]] = None
    loaded_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        self.last_used = datetime.now()

    def age_seconds(self) -> float:
        return (datetime.now() - self.loaded_at).total_seconds()

    def idle_seconds(self) -> float:
        return (datetime.now() - self.last_used).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "loaded_at": self.loaded_at.isoformat(),
            "last_used": self.last_used.isoformat(),
            "age_seconds": round(self.age_seconds(), 2),
            "idle_seconds": round(self.idle_seconds(), 2),
            "metadata": self.metadata,
        }


class ModelCache:
    """Tracks loaded models and unload callbacks without owning model internals."""

    def __init__(self):
        self.entries: Dict[str, ModelCacheEntry] = {}

    def register(self, name: str, model: Any = None, unload_callback: Callable[[], None] | None = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.entries[name] = ModelCacheEntry(name=name, model=model, unload_callback=unload_callback, metadata=metadata or {})

    def touch(self, name: str) -> None:
        if name in self.entries:
            self.entries[name].touch()

    def unregister(self, name: str) -> None:
        self.entries.pop(name, None)

    def unload(self, name: str) -> bool:
        entry = self.entries.get(name)
        if not entry:
            return False
        if entry.unload_callback:
            entry.unload_callback()
        self.entries.pop(name, None)
        self._cleanup()
        return True

    def unload_idle(self, idle_seconds: float) -> List[str]:
        unloaded: list[str] = []
        for name, entry in list(self.entries.items()):
            if entry.idle_seconds() >= idle_seconds:
                if self.unload(name):
                    unloaded.append(name)
        return unloaded

    def unload_all(self) -> List[str]:
        unloaded: list[str] = []
        for name in list(self.entries):
            if self.unload(name):
                unloaded.append(name)
        return unloaded

    def stats(self) -> Dict[str, Any]:
        return {"count": len(self.entries), "models": [entry.to_dict() for entry in self.entries.values()]}

    def _cleanup(self) -> None:
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
