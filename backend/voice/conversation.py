"""Continuous voice conversation state for JARVIS."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import time
from uuid import uuid4


class VoiceSessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    PAUSED = "paused"


@dataclass(slots=True)
class VoiceTurn:
    speaker: str
    text: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class VoiceConversationSession:
    id: str = field(default_factory=lambda: f"voice_{uuid4().hex[:10]}")
    state: VoiceSessionState = VoiceSessionState.IDLE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity_monotonic: float = field(default_factory=time.monotonic)
    idle_timeout_seconds: int = 45
    wake_word_required_first_turn: bool = True
    turns: List[VoiceTurn] = field(default_factory=list)
    current_topic: str = ""

    @property
    def active(self) -> bool:
        return self.state != VoiceSessionState.IDLE and not self.is_expired()

    def is_expired(self) -> bool:
        return (time.monotonic() - self.last_activity_monotonic) > self.idle_timeout_seconds

    def touch(self) -> None:
        self.last_activity_monotonic = time.monotonic()

    def start(self) -> None:
        self.state = VoiceSessionState.LISTENING
        self.touch()

    def pause(self) -> None:
        self.state = VoiceSessionState.PAUSED
        self.touch()

    def resume(self) -> None:
        self.state = VoiceSessionState.LISTENING
        self.touch()

    def end(self) -> None:
        self.state = VoiceSessionState.IDLE
        self.touch()

    def add_turn(self, speaker: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> VoiceTurn:
        turn = VoiceTurn(speaker=speaker, text=text.strip(), metadata=metadata or {})
        self.turns.append(turn)
        self.turns = self.turns[-20:]
        self.touch()
        if speaker == "user" and text.strip():
            self.current_topic = self._infer_topic(text)
        return turn

    def context_prompt(self) -> str:
        recent = self.turns[-6:]
        if not recent:
            return ""
        lines = [f"{turn.speaker}: {turn.text}" for turn in recent]
        return "Recent voice context:\n" + "\n".join(lines)

    def should_accept_followup(self) -> bool:
        return self.active and self.state in {VoiceSessionState.LISTENING, VoiceSessionState.PROCESSING, VoiceSessionState.SPEAKING}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state.value,
            "created_at": self.created_at,
            "idle_timeout_seconds": self.idle_timeout_seconds,
            "wake_word_required_first_turn": self.wake_word_required_first_turn,
            "seconds_since_activity": round(time.monotonic() - self.last_activity_monotonic, 2),
            "active": self.active,
            "expired": self.is_expired(),
            "current_topic": self.current_topic,
            "turns": [turn.to_dict() for turn in self.turns],
        }

    def _infer_topic(self, text: str) -> str:
        words = [w.strip(".,!?;:") for w in text.lower().split() if len(w.strip(".,!?;:")) > 3]
        return " ".join(words[:8])


class VoiceConversationManager:
    def __init__(self, idle_timeout_seconds: int = 45, wake_word_required_first_turn: bool = True):
        self.idle_timeout_seconds = idle_timeout_seconds
        self.wake_word_required_first_turn = wake_word_required_first_turn
        self.session = VoiceConversationSession(
            idle_timeout_seconds=idle_timeout_seconds,
            wake_word_required_first_turn=wake_word_required_first_turn,
        )

    def on_wake_word(self) -> VoiceConversationSession:
        if self.session.is_expired() or self.session.state == VoiceSessionState.IDLE:
            self.session = VoiceConversationSession(
                idle_timeout_seconds=self.idle_timeout_seconds,
                wake_word_required_first_turn=self.wake_word_required_first_turn,
            )
        self.session.start()
        return self.session

    def accept_text(self, text: str) -> str:
        self.session.state = VoiceSessionState.PROCESSING
        self.session.add_turn("user", text)
        return self.session.context_prompt()

    def add_assistant_response(self, text: str) -> None:
        self.session.add_turn("assistant", text)
        self.session.state = VoiceSessionState.SPEAKING

    def mark_listening(self) -> None:
        self.session.state = VoiceSessionState.LISTENING
        self.session.touch()

    def pause(self) -> None:
        self.session.pause()

    def resume(self) -> None:
        self.session.resume()

    def end(self) -> None:
        self.session.end()

    def to_dict(self) -> Dict[str, Any]:
        return self.session.to_dict()
