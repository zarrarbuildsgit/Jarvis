"""
JARVIS Voice - Text-to-Speech Engine
F5-TTS with voice cloning support
"""

import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from typing import Optional
from loguru import logger
import asyncio
import time

class TTSEngine:
    """Text-to-Speech with F5-TTS voice cloning"""
    
    def __init__(self, voice_sample_path: Optional[str] = None):
        self.model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.voice_sample_path = voice_sample_path
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize F5-TTS model"""
        try:
            from f5_tts.infer.utils_infer import load_model
            from f5_tts.model import DiT

            self.model = load_model(
                model_cls=DiT,
                model_cfg=dict(dim=1024, depth=22, heads=16, ff_mult=2, text_dim=512, conv_layers=4),
                ckpt_path=str(self._get_checkpoint_path()),
                ode_method="euler",
                use_ema=True,
                device=self.device
            )
            logger.info(f"✓ F5-TTS model loaded on {self.device}")
        except Exception as e:
            logger.warning(f"F5-TTS initialization failed: {e}")
            self.model = None
    
    def _get_checkpoint_path(self) -> Optional[Path]:
        """Get path to F5-TTS checkpoint"""
        checkpoints = [
            Path("models/f5_tts/F5TTS_Base/model_1200000.pt"),
            Path("models/f5_tts/model_1200000.pt"),
        ]
        for cp in checkpoints:
            if cp.exists():
                return cp
        return None
    
    def clone_voice(self, sample_path: str, output_path: str) -> bool:
        """Clone voice from audio sample"""
        logger.info(f"Cloning voice from {sample_path}")
        sample_path = Path(sample_path)
        
        if not sample_path.exists():
            logger.error(f"Voice sample not found: {sample_path}")
            return False
        
        try:
            audio, sr = sf.read(str(sample_path))
            if sr != 24000:
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=24000)
                sr = 24000
            
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            config = {
                "sample_path": str(sample_path),
                "sample_rate": 24000,
                "audio_length": len(audio),
                "device": self.device
            }
            import json
            with open(str(output_dir / "voice_config.json"), 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"✓ Voice clone configuration saved to {output_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Voice cloning failed: {e}")
            return False
    
    def synthesize(self, text: str, output_path: Optional[str] = None, 
                   ref_audio: Optional[str] = None, ref_text: Optional[str] = None) -> Optional[str]:
        """Synthesize speech from text"""
        if self.model is None:
            logger.error("TTS model not initialized")
            return None
        
        try:
            text = text.strip()
            if not text:
                return None
            
            # Reference audio for voice cloning
            if ref_audio is None and self.voice_sample_path:
                ref_audio = self.voice_sample_path
            
            if ref_audio is None:
                logger.error("No reference audio provided for voice cloning")
                return None
            
            ref_audio_path = Path(ref_audio)
            if not ref_audio_path.exists():
                logger.error(f"Reference audio not found: {ref_audio_path}")
                return None
            
            # Load reference audio
            ref_audio_data, ref_sr = sf.read(str(ref_audio_path))
            
            if ref_text is None:
                ref_text = "This is a reference audio sample for voice cloning."
            
            # Generate audio using F5-TTS
            from f5_tts.infer.utils_infer import infer_process
            from f5_tts.model.utils import convert_char_to_pinyin
            
            ref_audio_tensor = torch.from_numpy(ref_audio_data).float().to(self.device)
            
            text_tokens = convert_char_to_pinyin([text])
            ref_text_tokens = convert_char_to_pinyin([ref_text])
            
            audio, sample_rate = infer_process(
                ref_audio=ref_audio_tensor,
                ref_text=ref_text_tokens[0],
                gen_text=text_tokens[0],
                model_obj=self.model,
                cross_fade_duration=0.15
            )
            
            if output_path is None:
                output_path = f"data/voice_output/tts_{int(time.time())}.wav"
            
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), audio, sample_rate)
            
            logger.info(f"✓ TTS output saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None
    
    async def synthesize_async(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Async version of synthesize"""
        return await asyncio.to_thread(self.synthesize, text, output_path)
    
    def get_model_info(self) -> dict:
        return {
            "model": "F5-TTS" if self.model else "Not loaded",
            "device": self.device,
            "voice_sample": self.voice_sample_path or "Default"
        }
