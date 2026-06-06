"""Audio playback/session helpers for voice mode."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict


class AudioPlaybackState(str, Enum):
    IDLE = "idle"
    PLAYING = "playing"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(slots=True)
class AudioPlaybackStatus:
    state: AudioPlaybackState = AudioPlaybackState.IDLE
    current_file: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data


class AudioPlaybackController:
    """Controls TTS playback and supports barge-in stop."""

    def __init__(self):
        self.status = AudioPlaybackStatus()

    def stop(self) -> None:
        self.status.state = AudioPlaybackState.STOPPING
        try:
            import sounddevice as sd
            sd.stop()
        except Exception as exc:
            self.status.error = str(exc)

    def mark_playing(self, filepath: str) -> None:
        self.status = AudioPlaybackStatus(AudioPlaybackState.PLAYING, filepath, "")

    def mark_idle(self) -> None:
        self.status = AudioPlaybackStatus()

    def mark_error(self, error: str) -> None:
        self.status = AudioPlaybackStatus(AudioPlaybackState.ERROR, self.status.current_file, error)

    def is_playing(self) -> bool:
        return self.status.state == AudioPlaybackState.PLAYING

    def to_dict(self) -> Dict[str, Any]:
        return self.status.to_dict()
