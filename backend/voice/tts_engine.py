"""
JARVIS Phase 2: F5-TTS Voice Cloning Engine
Clone JARVIS voice from audio sample
"""

import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional
try:
    from loguru import logger
except Exception:  # pragma: no cover - minimal env fallback
    import logging
    logger = logging.getLogger(__name__)
import time

class F5TTSEngine:
    def __init__(self, voice_sample: Optional[str] = None):
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.voice_sample = voice_sample
        self._loaded = False
    
    def load_model(self):
        """Load F5-TTS model"""
        if self._loaded: return True
        
        try:
            from f5_tts.infer.utils_infer import load_model
            from f5_tts.model import DiT
            
            checkpoint = self._find_checkpoint()
            if not checkpoint:
                logger.warning("F5-TTS checkpoint not found. Run: uv run python scripts/download_models.py")
                return False
            
            self.model = load_model(
                model_cls=DiT,
                model_cfg=dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                ckpt_path=str(checkpoint),
                ode_method="euler",
                use_ema=True,
                device=self.device
            )
            self._loaded = True
            logger.info(f"✅ F5-TTS loaded on {self.device}")
            return True
            
        except Exception as e:
            logger.error(f"❌ F5-TTS load failed: {e}")
            return False
    
    def _find_checkpoint(self) -> Optional[Path]:
        """Find F5-TTS checkpoint file"""
        search_paths = [
            Path("models/f5_tts/F5TTS_Base/model_1200000.pt"),
            Path("models/f5_tts/model_1200000.pt"),
            Path.home() / ".cache" / "huggingface" / "hub" / "models--SWivid--F5-TTS",
        ]
        for p in search_paths:
            if p.exists() and p.is_file():
                return p
        return None
    
    def clone_voice(self, sample_path: str, output_dir: str) -> bool:
        """Clone voice from audio sample"""
        sample_path = Path(sample_path)
        if not sample_path.exists():
            logger.error(f"Sample not found: {sample_path}")
            return False
        
        try:
            audio, sr = sf.read(str(sample_path))
            if sr != 24000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=24000)
                sr = 24000
            
            output = Path(output_dir)
            output.mkdir(parents=True, exist_ok=True)
            
            import json
            config = {
                "sample_path": str(sample_path),
                "sample_rate": 24000,
                "audio_length": len(audio),
                "device": self.device,
                "created_at": time.time()
            }
            with open(output / "voice_config.json", 'w') as f:
                json.dump(config, f, indent=2)
            
            self.voice_sample = str(sample_path)
            logger.info(f"✅ Voice cloned from {sample_path.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Voice cloning failed: {e}")
            return False
    
    def speak(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Synthesize speech from text using cloned voice"""
        if not self._loaded:
            if not self.load_model():
                return None
        
        text = text.strip()
        if not text:
            return None
        
        try:
            from f5_tts.infer.utils_infer import infer_process
            from f5_tts.model.utils import convert_char_to_pinyin
            
            # Reference audio (cloned voice)
            ref_audio_path = Path(self.voice_sample)
            if not ref_audio_path.exists():
                logger.error("No voice sample configured")
                return None
            
            ref_audio_data, ref_sr = sf.read(str(ref_audio_path))
            ref_text = "This is a reference audio sample for voice cloning."
            
            ref_tensor = torch.from_numpy(ref_audio_data).float().to(self.device)
            text_tokens = convert_char_to_pinyin([text])
            ref_tokens = convert_char_to_pinyin([ref_text])
            
            audio, sample_rate = infer_process(
                ref_audio=ref_tensor,
                ref_text=ref_tokens[0],
                gen_text=text_tokens[0],
                model_obj=self.model,
                cross_fade_duration=0.15
            )
            
            if output_path is None:
                output_path = f"data/voice_output/tts_{int(time.time())}.wav"
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, audio, sample_rate)
            
            logger.info(f"✅ Speech saved to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ TTS synthesis failed: {e}")
            return None
    
    def get_info(self) -> dict:
        return {
            "engine": "F5-TTS",
            "loaded": self._loaded,
            "device": self.device,
            "voice_sample": self.voice_sample or "Not configured"
        }
