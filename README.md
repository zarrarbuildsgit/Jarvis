# 🤖 J.A.R.V.I.S. — Just A Rather Very Intelligent System

> A fully local AI computer control agent for Windows. Sees your screen, understands voice commands, and executes tasks autonomously with built-in safety verification.

## 🚀 Quick Start

```powershell
# 1. Install dependencies
uv venv && uv sync
cd ui-server && npm install && cd ..

# 2. Download AI models (first run, ~5-10GB)
uv run python scripts/download_models.py

# 3. Start JARVIS
uv run python main.py --phase 1
```

## 🏗️ Architecture

### Multi-Model Vision Routing
```
Screen Capture → SmolVLM (fast checks, ~200ms)
              → Florence-2 (UI element detection)
              → Qwen2.5-VL-3B (complex reasoning, ~1-2s)
```

### Anti-Hallucination Verification Loop
```
Plan → Execute → Screenshot → Verify → If Fail → Retry/Escalate
```

### Trust Level System
| Level | Description | Allowed |
|-------|------------|---------|
| 1 | New | Read-only, view screen |
| 2 | Proven | Create files, type, click |
| 3 | Trusted | Install, modify, delete |
| 4 | Full | Unrestricted access |

Auto-promotes based on success rate (90%+ required per level).

### Memory Architecture
- **Episodic**: Past actions, outcomes, context
- **Semantic**: Learned facts, patterns, rules
- Both stored in ChromaDB with vector similarity search

## 📁 Project Structure

```
JARVIS/
├── backend/
│   ├── agent/         # CrewAI multi-agent system
│   │   ├── crew.py    # Agent orchestration
│   │   ├── tools.py   # Terminal, file, screen tools
│   │   └── verifier.py # Anti-hallucination verification
│   ├── vision/        # Multi-model vision routing
│   │   └── model_router.py
│   ├── voice/         # STT + TTS engines
│   │   ├── stt.py     # NVIDIA Canary → faster-whisper
│   │   └── tts.py     # F5-TTS with voice cloning
│   ├── memory/        # ChromaDB episodic + semantic
│   │   └── chroma_memory.py
│   ├── screen/        # Screen capture + control
│   │   ├── capture.py # DXCam + mss
│   │   └── control.py # pywinauto + uiautomation
│   ├── security/      # Trust level management
│   │   └── trust.py
│   └── api.py         # FastAPI backend
├── frontend/          # SvelteKit dashboard
├── ui-server/         # Express.js API server
├── overlay/           # Transparent desktop widget
├── scripts/           # Setup and utilities
├── data/              # Memory, logs, voice samples
├── models/            # Cached AI models
└── main.py            # Entry point
```

## 🧠 AI Models

### Vision (Phase 1)
| Model | Purpose | VRAM | Speed |
|-------|---------|------|-------|
| SmolVLM-500M | Quick checks | CPU | ~200ms |
| Florence-2-base | UI detection | ~2GB | ~500ms |
| Qwen2.5-VL-3B | Complex reasoning | ~4GB | ~1-2s |

### Voice (Phase 2)
| Engine | Role | Notes |
|--------|------|-------|
| NVIDIA Canary 1B | Primary STT | GPU optimized |
| faster-whisper | Fallback STT | CPU friendly |
| F5-TTS | TTS with cloning | Best open-source voice clone |

### Memory
- **ChromaDB**: Vector database for episodic + semantic memory
- **Adaptive Context**: Dynamically sizes context window (4K-32K tokens)

## 🛡️ Safety Features

1. **Command Blocking**: Dangerous commands (rm -rf /, shutdown, etc.) are blocked
2. **Verification Loop**: Every action is verified via screenshot analysis
3. **Trust Levels**: Gradual permission escalation based on proven reliability
4. **Checkpoint Recovery**: State saved before each action for rollback
5. **Fallback Chain**: Multiple models ensure reliability

## 📋 Usage

### Interactive Mode
```
You: Open Notepad and type "Hello World"
🤔 JARVIS is thinking...
✅ Task Complete: Successfully opened Notepad and typed "Hello World"
```

### Slash Commands
| Command | Description |
|---------|-------------|
| `/help` | Show commands |
| `/exit` | Shut down |
| `/status` | System status |
| `/memory` | Memory stats |
| `/trust` | Trust level |
| `/clear` | Clear terminal |

### Natural Commands
- "Open Chrome and go to google.com"
- "List all files in Documents"
- "Create a Python file called test.py"
- "Read config.json"
- "Click the Save button"
- "What's on my screen?"

## 🔧 Voice Setup (Phase 2)

### Record Voice Sample
1. Use Audacity or Voice Recorder
2. Record 6-30 seconds of clear speech
3. Save as WAV, 22050 Hz, 16-bit
4. Place in `data/voice_samples/jarvis_voice.wav`

### Clone Voice
```powershell
uv run python scripts/setup_voice.py
```

### Tips for Best Cloning
- Speak naturally (don't over-enunciate)
- Quiet room, good microphone
- Multiple samples = better quality

## 🖥️ Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | GTX 1050 Ti (4GB) | RTX 3060 (12GB) |
| RAM | 16GB | 32GB |
| Storage | 20GB free | 50GB+ SSD |
| CPU | Intel i7 7th Gen | Intel i9 / AMD Ryzen 9 |

## 🐛 Troubleshooting

### GPU Not Detected
```powershell
nvcc --version
nvidia-smi
winget install NVIDIA.CUDA
```

### Out of Memory
- Close other apps
- Use SmolVLM only (edit `backend/config/settings.yaml`)
- Set `gpu: "cpu"` in settings

### Model Download Fails
```powershell
rm -rf ~/.cache/huggingface
uv run python scripts/download_models.py
```

## 📈 Roadmap

- ✅ **Phase 1**: Core agent + screen control + verification
- 🔜 **Phase 2**: Voice engine (STT + TTS + wake word)
- 🔜 **Phase 3**: UI dashboard + overlay completion
- 🔜 **Phase 4**: Browser automation + API integrations

---

**JARVIS is not affiliated with Marvel or Disney. Personal use only.**
