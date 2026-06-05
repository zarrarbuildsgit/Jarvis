"""
JARVIS Voice - Speech-to-Text Engine
NVIDIA Canary → faster-whisper fallback
"""

import numpy as np
from pathlib import Path
from typing import Optional, Generator
import torch
from loguru import logger

class STTEngine:
    """Speech-to-Text with automatic fallback chain"""
    
    def __init__(self):
        self.primary_model = None  # NVIDIA Canary
        self.fallback_model = None  # faster-whisper
        self.vad_model = None  # Silero VAD
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize STT models with graceful fallback"""
        # 1. Try NVIDIA Canary (GPU optimized)
        try:
            from nemo.collections.asr.models import CanaryModel
            self.primary_model = CanaryModel.from_pretrained("nvidia/canary-1b")
            self.primary_model.to(self.device)
            self.primary_model.eval()
            logger.info(f"✓ NVIDIA Canary loaded on {self.device}")
        except Exception as e:
            logger.warning(f"NVIDIA Canary failed: {e}")
            self.primary_model = None
        
        # 2. Always load faster-whisper as fallback
        try:
            from faster_whisper import WhisperModel
            model_size = "small" if self.device == "cuda" else "base"
            compute_type = "float16" if self.device == "cuda" else "int8"
            self.fallback_model = WhisperModel(
                model_size,
                device=self.device,
                compute_type=compute_type
            )
            logger.info(f"✓ faster-whisper ({model_size}) loaded")
        except Exception as e:
            logger.error(f"faster-whisper failed: {e}")
            self.fallback_model = None
        
        # 3. Load VAD
        try:
            self.vad_model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False
            )
            self.vad_model.to(self.device)
            logger.info("✓ Silero VAD loaded")
        except Exception as e:
            logger.warning(f"VAD model failed: {e}")
            self.vad_model = None
    
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """Transcribe audio data"""
        if self.primary_model is not None:
            try:
                return self._transcribe_canary(audio_data, sample_rate)
            except Exception as e:
                logger.warning(f"Canary failed: {e}, using fallback")
        
        if self.fallback_model is not None:
            try:
                return self._transcribe_whisper(audio_data, sample_rate)
            except Exception as e:
                logger.error(f"Whisper failed: {e}")
        
        logger.error("No STT models available")
        return ""
    
    def _transcribe_canary(self, audio_data: np.ndarray, sample_rate: int) -> str:
        audio_tensor = torch.from_numpy(audio_data).float().to(self.device)
        with torch.no_grad():
            result = self.primary_model.transcribe(audio_tensor, sample_rate=sample_rate)
        return result[0]["text"] if result else ""
    
    def _transcribe_whisper(self, audio_data: np.ndarray, sample_rate: int) -> str:
        segments, _ = self.fallback_model.transcribe(audio_data, beam_size=5, language="en")
        return " ".join([segment.text for segment in segments])
    
    def is_silence(self, audio_chunk: np.ndarray, sample_rate: int = 16000) -> bool:
        """Check if audio chunk contains speech or silence"""
        if self.vad_model is None:
            energy = np.mean(audio_chunk ** 2)
            return energy < 0.001
        
        audio_tensor = torch.from_numpy(audio_chunk).float().to(self.device)
        speech_prob = self.vad_model(audio_tensor, sample_rate).item()
        return speech_prob < 0.5
    
    def get_model_info(self) -> dict:
        return {
            "primary": "NVIDIA Canary" if self.primary_model else "Not loaded",
            "fallback": "faster-whisper" if self.fallback_model else "Not loaded",
            "vad": "Silero VAD" if self.vad_model else "Not loaded",
            "device": self.device
        }
