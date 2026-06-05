# 🗣️ JARVIS Voice Clone Setup Guide

## Important Finding
**Kokoro TTS does NOT support voice cloning.** The developer explicitly ruled it out.

**Solution: F5-TTS** — the best open-source voice cloning model available in 2025/2026.

## Requirements
- F5-TTS installed (`pip install f5-tts`)
- Clean audio sample (6-30 seconds)
- Quiet recording environment
- WAV format, 24000 Hz, 16-bit preferred

## Step 1: Record Audio Sample
- Speak clearly and naturally
- Use a good microphone
- Avoid background noise
- Record 6-30 seconds of continuous speech
- Save as `data/voice_samples/jarvis_voice.wav`

### Tips for JARVIS-like Voice
1. Use a calm, authoritative tone (think Paul Bettany's JARVIS)
2. Speak at a moderate pace
3. Avoid emotional extremes
4. Multiple samples (3-5) = significantly better quality

## Step 2: Process with F5-TTS
```bash
# Install F5-TTS
pip install f5-tts

# Run voice cloning
python scripts/clone_voice.py \
    --reference data/voice_samples/jarvis_voice.wav \
    --output data/voice_models/jarvis_clone \
    --epochs 100
```

## Step 3: Test the Clone
```bash
python scripts/test_voice.py \
    --model data/voice_models/jarvis_clone \
    --text "Hello, I am JARVIS. How can I assist you today?"
```

## Alternatives if F5-TTS Doesn't Work
1. **XTTS v2** — Voice cloning with 6-second sample
2. **Fish Speech** — Newer model, good quality
3. **StyleTTS2** — Can build custom voice models

## Troubleshooting
- **Poor Quality**: Try longer/more samples, ensure quiet recording
- **Robotic Voice**: Check sample quality, increase epochs
- **Out of Memory**: Reduce batch size or use CPU
- **Model Not Found**: Run `uv run python scripts/download_models.py`
