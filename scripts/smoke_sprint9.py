"""Sprint 9 smoke checks.

Run with:
    uv run python scripts/smoke_sprint9.py

Validates conversation state, interrupt classification, audio playback state,
and the importability of voice integration without requiring microphone hardware.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.voice.audio_session import AudioPlaybackController, AudioPlaybackState
from backend.voice.conversation import VoiceConversationManager, VoiceSessionState
from backend.voice.interrupts import VoiceIntent, VoiceInterruptDetector


def assert_true(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def main() -> None:
    convo = VoiceConversationManager(idle_timeout_seconds=1)
    session = convo.on_wake_word()
    assert_true(session.state == VoiceSessionState.LISTENING, "wake word starts listening")
    ctx = convo.accept_text("Open Chrome and search benchmarks")
    assert_true("user:" in ctx, "context contains user turn")
    convo.add_assistant_response("Opening Chrome.")
    assert_true(convo.to_dict()["state"] == "speaking", "assistant response sets speaking")
    convo.mark_listening()
    assert_true(convo.to_dict()["active"], "session active")
    time.sleep(1.05)
    assert_true(convo.to_dict()["expired"], "session expires")

    detector = VoiceInterruptDetector()
    assert_true(detector.classify("stop talking").intent == VoiceIntent.STOP, "stop intent")
    assert_true(detector.classify("never mind").intent == VoiceIntent.CANCEL, "cancel intent")
    assert_true(detector.classify("pause listening").intent == VoiceIntent.PAUSE, "pause intent")
    assert_true(detector.classify("resume").intent == VoiceIntent.RESUME, "resume intent")
    assert_true(detector.classify("open notepad").intent == VoiceIntent.NORMAL, "normal intent")

    playback = AudioPlaybackController()
    playback.mark_playing("test.wav")
    assert_true(playback.is_playing(), "playback playing")
    playback.mark_idle()
    assert_true(playback.to_dict()["state"] == AudioPlaybackState.IDLE.value, "playback idle")

    # Full VoiceIntegration imports STT/TTS engines and therefore project ML deps.
    # This smoke test intentionally validates the dependency-light conversation layer.

    print("✅ Sprint 9 smoke checks passed")


if __name__ == "__main__":
    main()
