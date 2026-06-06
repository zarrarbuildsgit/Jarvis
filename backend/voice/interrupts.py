"""Voice interruption and command classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VoiceIntent(str, Enum):
    NORMAL = "normal"
    STOP = "stop"
    CANCEL = "cancel"
    PAUSE = "pause"
    RESUME = "resume"
    SLEEP = "sleep"
    STATUS = "status"


@dataclass(slots=True)
class VoiceIntentResult:
    intent: VoiceIntent
    matched_phrase: str = ""
    should_process_agent: bool = True
    response: str = ""

    def to_dict(self):
        return {
            "intent": self.intent.value,
            "matched_phrase": self.matched_phrase,
            "should_process_agent": self.should_process_agent,
            "response": self.response,
        }


class VoiceInterruptDetector:
    PHRASES = {
        VoiceIntent.STOP: ["stop", "stop talking", "be quiet", "silence", "shut up"],
        VoiceIntent.CANCEL: ["cancel", "cancel that", "never mind", "nevermind", "abort", "forget it"],
        VoiceIntent.PAUSE: ["pause", "pause listening", "hold on", "stand by"],
        VoiceIntent.RESUME: ["resume", "continue", "keep going", "i'm back", "im back"],
        VoiceIntent.SLEEP: ["go to sleep", "sleep", "that's all", "that is all", "thanks jarvis"],
        VoiceIntent.STATUS: ["voice status", "are you listening", "conversation status"],
    }

    RESPONSES = {
        VoiceIntent.STOP: "Stopping speech.",
        VoiceIntent.CANCEL: "Cancelled.",
        VoiceIntent.PAUSE: "Paused. Say resume when ready.",
        VoiceIntent.RESUME: "Resuming.",
        VoiceIntent.SLEEP: "Going quiet.",
        VoiceIntent.STATUS: "Voice session is active.",
    }

    def classify(self, text: str) -> VoiceIntentResult:
        normalized = " ".join(text.lower().strip().split())
        if not normalized:
            return VoiceIntentResult(VoiceIntent.NORMAL)
        for intent, phrases in self.PHRASES.items():
            for phrase in phrases:
                if normalized == phrase or normalized.startswith(phrase + " "):
                    return VoiceIntentResult(
                        intent=intent,
                        matched_phrase=phrase,
                        should_process_agent=False,
                        response=self.RESPONSES.get(intent, "OK."),
                    )
        return VoiceIntentResult(VoiceIntent.NORMAL)
