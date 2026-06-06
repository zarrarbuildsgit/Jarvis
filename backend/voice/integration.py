"""
JARVIS Voice Integration - Phase 2
Connects Voice (STT/TTS/WakeWord) to the Agent Crew
"""

import asyncio
import numpy as np
import time
from typing import Optional, Callable
from pathlib import Path
try:
    from loguru import logger
except Exception:  # pragma: no cover - minimal env fallback
    import logging
    logger = logging.getLogger(__name__)

from backend.voice.audio_session import AudioPlaybackController
from backend.voice.conversation import VoiceConversationManager
from backend.voice.interrupts import VoiceIntent, VoiceInterruptDetector
from backend.voice.stt_engine import STTEngine
from backend.voice.tts_engine import F5TTSEngine
from backend.voice.wake_word import WakeWordDetector

class VoiceIntegration:
    """
    Manages the full voice pipeline:
    Wake Word -> STT -> Agent -> TTS -> Speaker
    
    Designed for Phase 5: continuous voice conversations
    """
    
    def __init__(self, agent_crew, trust_manager, continuous: bool = False, idle_timeout_seconds: int = 45):
        self.stt = STTEngine()
        self.tts = F5TTSEngine()
        self.wake_word = WakeWordDetector()
        self.agent = agent_crew
        self.trust = trust_manager
        self.continuous = continuous
        self.idle_timeout_seconds = idle_timeout_seconds
        self.conversation = VoiceConversationManager(
            idle_timeout_seconds=idle_timeout_seconds,
            wake_word_required_first_turn=True,
        )
        self.interrupts = VoiceInterruptDetector()
        self.playback = AudioPlaybackController()
        self._recording = False
        self._last_interaction = 0.0
        self._cancel_requested = False
        
        # Audio config
        self.sample_rate = 16000
        self.chunk_duration = 0.05  # 50ms chunks
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        
        # State
        self._listening = False
        self._processing = False
        self._audio_stream = None
        self._pyaudio = None
        self._loop = None
        
        # Callbacks
        self.on_voice_command = None
        self.on_tts_start = None
        self.on_tts_end = None
        self.on_state_change = None
        
    def initialize(self):
        """Initialize all voice components"""
        logger.info("Initializing Voice Integration...")
        
        # Load STT (lazy-load models)
        self.stt._load_fallback()  # Always load fallback
        self.stt._load_vad()       # Load VAD for silence detection
        
        # Load TTS
        self.tts.load_model()
        
        # Setup wake word
        self.wake_word.load_model()
        self.wake_word.set_callback(self._on_wake_word)
        
        logger.info("✅ Voice Integration initialized")
    
    async def start_voice_loop(self):
        """Main voice interaction loop"""
        self._listening = True
        try:
            import pyaudio
        except Exception as exc:
            logger.error(f"❌ PyAudio unavailable: {exc}")
            return
        self._pyaudio = pyaudio.PyAudio()
        
        # Find best mic
        device_index = self._find_mic()
        if device_index is None:
            logger.error("❌ No microphone found")
            return
        
        self._audio_stream = self._pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.chunk_size
        )
        
        logger.info(f"🎤 Mic active: {self._pyaudio.get_device_info_by_index(device_index)['name']}")
        logger.info("👂 Say 'Hey JARVIS' to start...")
        
        # Start wake word listener
        self.wake_word.start()
        
        # Main loop
        try:
            audio_buffer = []
            silence_count = 0
            
            while self._listening:
                try:
                    chunk = self._audio_stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    if self._recording:
                        audio_buffer.append(audio_data)
                        
                        # Check for silence
                        if self.stt.is_voice_active(audio_data, threshold=0.3):
                            silence_count = 0
                        else:
                            silence_count += 1
                        
                        # If 1 second of silence, stop recording
                        if silence_count > 20:  # 20 * 50ms = 1s
                            self._recording = False
                            await self._process_voice_command(audio_buffer)
                            audio_buffer = []
                            silence_count = 0
                    else:
                        # In continuous mode, keep listening for follow-ups for a short window
                        if self.continuous and self._last_interaction and (time.time() - self._last_interaction) < self.idle_timeout_seconds:
                            if self.stt.is_voice_active(audio_data, threshold=0.35):
                                self._recording = True
                                audio_buffer = [audio_data]
                                silence_count = 0
                        # Otherwise wake_word detector is responsible for setting _recording.
                        
                except Exception as e:
                    logger.warning(f"Audio read error: {e}")
                    await asyncio.sleep(0.01)
        
        except KeyboardInterrupt:
            logger.info("Voice loop interrupted")
        finally:
            self.stop_voice_loop()
    
    def _on_wake_word(self):
        """Called when wake word is detected"""
        self._listening = True
        self._recording = True
        self._last_interaction = time.time()
        self.conversation.on_wake_word()
        self._emit_state()
        logger.info("🔔 Wake word detected - listening...")
        
        # Visual feedback
        if self.on_tts_start:
            self.on_tts_start("Listening...")
    
    async def _process_voice_command(self, audio_buffer: list):
        """Process recorded audio through STT -> Agent -> TTS"""
        if self._processing:
            return
        
        self._processing = True
        try:
            # 1. Transcribe
            audio_data = np.concatenate(audio_buffer)
            text = self.stt.transcribe(audio_data, self.sample_rate)
            
            if not text.strip():
                logger.info("⚠️ No speech detected")
                return
            
            logger.info(f"🎤 You said: '{text}'")
            self._last_interaction = time.time()

            # 2. Interruption / conversation commands
            intent = self.interrupts.classify(text)
            if intent.intent != VoiceIntent.NORMAL:
                await self._handle_voice_intent(intent)
                return

            context_prompt = self.conversation.accept_text(text)
            self._emit_state()
            enriched_text = text
            if self.continuous and context_prompt:
                enriched_text = f"{text}\n\n{context_prompt}"

            # 3. Send to agent
            if self.on_voice_command:
                self.on_voice_command(text)
            
            result = await self.agent.process_command(enriched_text, self.trust)
            logger.info(f"🤖 Agent response: {result}")
            self.conversation.add_assistant_response(str(result))
            self._last_interaction = time.time()
            self._emit_state()
            
            # 4. Speak response
            if self.tts.model:
                output_path = self.tts.speak(str(result))
                if output_path:
                    await self._play_audio(output_path)
            self.conversation.mark_listening()
            self._emit_state()
            
        except Exception as e:
            logger.error(f"❌ Voice processing failed: {e}")
        finally:
            self._processing = False
    
    async def _play_audio(self, filepath: str):
        """Play audio file through speakers"""
        try:
            import sounddevice as sd
            import soundfile as sf
            
            data, fs = sf.read(filepath)
            self.playback.mark_playing(filepath)
            self._emit_state()
            
            if self.on_tts_start:
                self.on_tts_start("Speaking...")
            
            sd.play(data, fs)
            sd.wait()
            self.playback.mark_idle()
            
            if self.on_tts_end:
                self.on_tts_end("Done")
            self._emit_state()
                
        except Exception as e:
            self.playback.mark_error(str(e))
            self._emit_state()
            logger.error(f"❌ Audio playback failed: {e}")
    
    def _find_mic(self) -> Optional[int]:
        """Find the best microphone"""
        if not self._pyaudio:
            return None
        
        for i in range(self._pyaudio.get_device_count()):
            info = self._pyaudio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name = info['name'].lower()
                if 'mic' in name or 'input' in name or 'capture' in name:
                    return i
        
        # Fallback to default
        try:
            return self._pyaudio.get_default_input_device_info()['index']
        except:
            return None
    
    def stop_voice_loop(self):
        """Stop voice listening"""
        self._listening = False
        self._recording = False
        self.conversation.end()
        self.playback.stop()
        self.wake_word.stop()
        
        if self._audio_stream:
            self._audio_stream.stop_stream()
            self._audio_stream.close()
        
        if self._pyaudio:
            self._pyaudio.terminate()
        
        logger.info("🔇 Voice loop stopped")
        self._emit_state()

    async def _handle_voice_intent(self, intent):
        """Handle stop/cancel/pause/resume/sleep without sending to agent."""
        logger.info(f"Voice intent: {intent.intent.value}")
        if intent.intent == VoiceIntent.STOP:
            self.playback.stop()
            self.conversation.mark_listening()
        elif intent.intent == VoiceIntent.CANCEL:
            self._cancel_requested = True
            self.playback.stop()
            self.conversation.mark_listening()
        elif intent.intent == VoiceIntent.PAUSE:
            self.conversation.pause()
            self.playback.stop()
        elif intent.intent == VoiceIntent.RESUME:
            self.conversation.resume()
        elif intent.intent == VoiceIntent.SLEEP:
            self.conversation.end()
            self._recording = False
        elif intent.intent == VoiceIntent.STATUS:
            self.conversation.add_assistant_response(intent.response)
        self._last_interaction = time.time()
        self._emit_state()
        if intent.response and self.tts.model and intent.intent not in {VoiceIntent.STOP, VoiceIntent.CANCEL}:
            output_path = self.tts.speak(intent.response)
            if output_path:
                await self._play_audio(output_path)

    def _emit_state(self):
        if self.on_state_change:
            try:
                self.on_state_change(self.get_status())
            except Exception as exc:
                logger.warning(f"Voice state callback failed: {exc}")
    
    def get_status(self) -> dict:
        return {
            "listening": self._listening,
            "processing": self._processing,
            "recording": self._recording,
            "continuous": self.continuous,
            "cancel_requested": self._cancel_requested,
            "conversation": self.conversation.to_dict(),
            "playback": self.playback.to_dict(),
            "stt": self.stt.get_model_info(),
            "tts": self.tts.get_info(),
            "wake_word": "active" if self.wake_word._running else "inactive"
        }
