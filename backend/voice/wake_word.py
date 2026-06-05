"""
JARVIS Phase 2: Wake Word Detector
Listens for "Hey JARVIS" or custom wake word
"""

import numpy as np
import torch
from pathlib import Path
from loguru import logger
from typing import Optional, Callable
import queue
import threading
import time

class WakeWordDetector:
    def __init__(
        self, 
        wake_word: str = "hey jarvis",
        model_path: Optional[str] = None,
        threshold: float = 0.85,
        cooldown: float = 2.0
    ):
        self.wake_word = wake_word.lower()
        self.model_path = model_path
        self.threshold = threshold
        self.cooldown = cooldown
        self.last_detection = 0
        
        # Audio buffer
        self.sample_rate = 16000
        self.chunk_size = 1024  # ~64ms at 16kHz
        self.buffer_size = self.sample_rate * 2  # 2 seconds of audio
        self.audio_buffer = queue.Queue(maxsize=100)
        
        # State
        self._running = False
        self._thread = None
        self._model = None
        self._callback = None
        self._vad_model = None
        
    def load_model(self):
        """Load wake word detection model"""
        try:
            # Option 1: Porcupine (best for wake words)
            try:
                import pvporcupine
                self._model = pvporcupine.create(
                    access_key=self._get_porcupine_key(),
                    keywords=['jarvis']
                )
                logger.info("✅ Porcupine wake word detector loaded")
                return
            except ImportError:
                logger.warning("Porcupine not available, using Silero VAD + keyword match")
            
            # Option 2: Silero VAD + simple keyword matching
            self._vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )
            self._vad_model.eval()
            logger.info("✅ Silero VAD loaded for wake word detection")
            
        except Exception as e:
            logger.error(f"❌ Wake word model load failed: {e}")
            self._model = None
    
    def _get_porcupine_key(self) -> str:
        """Get Porcupine access key (free for personal use)"""
        import os
        key = os.getenv("PORCUPINE_ACCESS_KEY", "")
        if not key:
            logger.warning("PORCUPINE_ACCESS_KEY not set, using free tier")
        return key
    
    def set_callback(self, callback: Callable):
        """Set function to call when wake word detected"""
        self._callback = callback
    
    def start(self, device_index: int = None):
        """Start listening for wake word"""
        if self._running:
            return
        
        if self._model is None and self._vad_model is None:
            self.load_model()
        
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info(f"👂 Listening for wake word: '{self.wake_word}'")
    
    def stop(self):
        """Stop listening"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("🔇 Wake word detector stopped")
    
    def _listen_loop(self):
        """Main listening loop"""
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            
            # Find best input device
            device_index = self._get_best_device()
            if device_index is None:
                logger.error("No audio input device found")
                self._running = False
                return
            
            stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size
            )
            
            logger.info(f"🎤 Audio stream opened: {self._pyaudio.get_device_info_by_index(device_index)['name']}")
            
            # VAD state
            speech_frames = []
            silence_counter = 0
            min_speech_frames = 5  # Minimum speech to trigger analysis
            
            while self._running:
                try:
                    chunk = stream.read(self.chunk_size, exception_on_overflow=False)
                    audio_data = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
                    
                    if self._model:
                        # Porcupine mode
                        pcm = np.frombuffer(chunk, dtype=np.int16).tolist()
                        keyword_index = self._model.process(pcm)
                        if keyword_index >= 0:
                            self._on_wake_word_detected()
                    else:
                        # VAD + buffer mode
                        is_speech = self._is_speech(audio_data)
                        
                        if is_speech:
                            speech_frames.append(audio_data)
                            silence_counter = 0
                        else:
                            silence_counter += 1
                            if silence_counter > 10 and speech_frames:
                                # End of speech utterance
                                if len(speech_frames) >= min_speech_frames:
                                    # Check if wake word was said
                                    full_audio = np.concatenate(speech_frames)
                                    if self._check_wake_word(full_audio):
                                        self._on_wake_word_detected()
                                speech_frames = []
                                silence_counter = 0
                        
                        # Keep buffer manageable
                        if len(speech_frames) > 50:
                            speech_frames = speech_frames[-20:]
                
                except Exception as e:
                    if self._running:
                        logger.warning(f"Audio read error: {e}")
                    time.sleep(0.01)
            
            stream.stop_stream()
            stream.close()
            self._pyaudio.terminate()
            
        except Exception as e:
            logger.error(f"❌ Listen loop failed: {e}")
            self._running = False
    
    def _get_best_device(self) -> Optional[int]:
        """Find the best audio input device"""
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            
            # Look for devices with "mic" or "input" in name
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    name = info['name'].lower()
                    if 'mic' in name or 'input' in name or 'capture' in name:
                        p.terminate()
                        return i
            
            # Fallback to default
            default = p.get_default_input_device_info()
            p.terminate()
            return default['index']
            
        except Exception as e:
            logger.error(f"Failed to find audio device: {e}")
            return None
    
    def _is_speech(self, audio_data: np.ndarray) -> bool:
        """Check if audio chunk contains speech"""
        if self._vad_model is None:
            # Simple energy-based VAD
            energy = np.mean(audio_data ** 2)
            return energy > 0.001
        
        try:
            audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
            with torch.no_grad():
                speech_prob = self._vad_model(audio_tensor, self.sample_rate).item()
            return speech_prob > 0.5
        except:
            return False
    
    def _check_wake_word(self, audio_data: np.ndarray) -> bool:
        """Simple keyword matching (placeholder - would use actual model in production)"""
        # In production, this would use a proper wake word model
        # For now, we'll trigger on any speech above threshold
        energy = np.mean(audio_data ** 2)
        return energy > 0.01
    
    def _on_wake_word_detected(self):
        """Handle wake word detection"""
        now = time.time()
        if now - self.last_detection < self.cooldown:
            return  # Prevent rapid re-triggering
        
        self.last_detection = now
        logger.info(f"🔔 WAKE WORD DETECTED: '{self.wake_word}'")
        
        if self._callback:
            self._callback()
        else:
            logger.info("⚠️ No callback set for wake word")
