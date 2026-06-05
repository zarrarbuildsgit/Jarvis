"""
JARVIS Phase 2: Voice Engine
NVIDIA Canary (Primary STT) -> Faster-Whisper (Fallback)
"""

import torch
import numpy as np
from pathlib import Path
from loguru import logger
from typing import Optional

class STTEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.primary_model = None  # NVIDIA Canary
        self.fallback_model = None # Faster-Whisper
        self.vad_model = None      # Silero VAD for voice detection
        
        # We initialize on-demand to save RAM
        self._primary_loaded = False
        self._fallback_loaded = False
        self._vad_loaded = False

    def _load_primary(self):
        if self._primary_loaded: return
        try:
            from nemo.collections.asr.models import CanaryModel
            self.primary_model = CanaryModel.from_pretrained("nvidia/canary-1b")
            self.primary_model.to(self.device)
            self.primary_model.eval()
            self._primary_loaded = True
            logger.info(f"✅ NVIDIA Canary loaded on {self.device}")
        except Exception as e:
            logger.warning(f"⚠️ NVIDIA Canary failed: {e}")
            self.primary_model = None

    def _load_fallback(self):
        if self._fallback_loaded: return
        try:
            from faster_whisper import WhisperModel
            model_size = "small" if self.device == "cuda" else "base"
            compute_type = "float16" if self.device == "cuda" else "int8"
            self.fallback_model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=compute_type
            )
            self._fallback_loaded = True
            logger.info(f"✅ Faster-Whisper ({model_size}) loaded")
        except Exception as e:
            logger.error(f"❌ Faster-Whisper failed: {e}")

    def _load_vad(self):
        if self._vad_loaded: return
        try:
            import silero_vad
            self.vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )
            self.vad_model.to(self.device)
            self._vad_loaded = True
            logger.info("✅ Silero VAD loaded")
        except Exception as e:
            logger.warning(f"⚠️ Silero VAD failed: {e}")

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio data with automatic fallback"""
        
        # Try Primary (Canary)
        if self.primary_model is not None:
            try:
                if not self._primary_loaded: self._load_primary()
                audio_tensor = torch.from_numpy(audio_data).float().to(self.device)
                with torch.no_grad():
                    result = self.primary_model.transcribe(audio_tensor, sample_rate=sample_rate)
                if result: return result[0]["text"]
            except Exception as e:
                logger.warning(f"Canary inference failed: {e}, falling back")

        # Fallback (Whisper)
        if self.fallback_model is not None:
            try:
                if not self._fallback_loaded: self._load_fallback()
                segments, _ = self.fallback_model.transcribe(
                    audio_data, 
                    beam_size=5, 
                    language="en"
                )
                return " ".join([segment.text for segment in segments])
            except Exception as e:
                logger.error(f"Whisper inference failed: {e}")
        
        return ""

    def is_voice_active(self, audio_chunk: np.ndarray, threshold: float = 0.5) -> bool:
        """Check if audio chunk contains speech (VAD)"""
        if not self._vad_loaded: self._load_vad()
        if self.vad_model is None:
            # Simple energy-based fallback
            energy = np.mean(audio_chunk ** 2)
            return energy > 0.001
        
        audio_tensor = torch.from_numpy(audio_chunk).float().to(self.device)
        speech_prob = self.vad_model(audio_tensor, 16000).item()
        return speech_prob > threshold
