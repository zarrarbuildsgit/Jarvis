# 🚀 JARVIS Quickstart Guide

## Prerequisites

1. **Windows 10/11** with:
   - Python 3.11+ (https://www.python.org/downloads/)
   - UV package manager (https://docs.astral.sh/uv/)
   - Node.js 20+ (https://nodejs.org/)
   - NVIDIA GPU with 4GB+ VRAM (GTX 1050 Ti minimum)
   - 16GB+ RAM

2. **Visual Studio Build Tools**:
   ```powershell
   winget install Microsoft.VisualStudio.2022.BuildTools
   ```

## Installation

### Step 1: Install UV
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```

### Step 2: Setup Project
```powershell
cd JARVIS
uv venv
uv sync
```

### Step 3: Install Node Dependencies
```powershell
cd ui-server && npm install && cd ..
```

### Step 4: Download Models (~5-10GB, first run only)
```powershell
uv run python scripts/download_models.py
```

### Step 5: Start JARVIS
```powershell
# Terminal 1: FastAPI backend
uv run python backend/api.py

# Terminal 2: JARVIS agent
uv run python main.py --phase 5
```

## Usage

### Interactive Mode
```
You: Open Notepad and type "Hello World"
🤔 JARVIS is thinking...
✅ Task Complete: Successfully opened Notepad and typed "Hello World"
```

### Dashboard
Open `http://localhost:3001` for:
- Real-time chat
- Task assignment & monitoring
- Screen preview
- Memory viewer
- Trust level indicator

### Commands
| Command | Description |
|---------|-------------|
| `/help` | Show commands |
| `/exit` | Shut down |
| `/status` | System status |
| `/memory` | Memory stats |
| `/trust` | Trust level |
| `/clear` | Clear terminal |

### Easy Start
Double-click `start_jarvis.bat` to launch everything automatically.

## Voice Setup (Phase 2)

### Recording
1. Record 6-30 seconds of clear speech
2. Save as WAV, 22050 Hz, 16-bit
3. Place in `data/voice_samples/jarvis_voice.wav`

### Clone
```powershell
uv run python scripts/setup_voice.py
```

## Troubleshooting

### GPU Issues
```powershell
nvcc --version
nvidia-smi
```

### Memory Issues
- Close other apps
- Use SmolVLM only (edit `backend/config/settings.yaml`)

### Model Download
```powershell
rm -rf ~/.cache/huggingface
uv run python scripts/download_models.py
```

## Architecture

```
┌─────────────────────────────────────────┐
│              JARVIS System               │
├─────────────────────────────────────────┤
│  Vision ───┐                            │
│  Voice ────┼───► CrewAI Agent Core ────► │
│  Screen ───┤                            │
├────────────┴────────────────────────────┤
│  ChromaDB Memory (Episodic + Semantic)  │
├─────────────────────────────────────────┤
│  FastAPI Backend ───► SvelteKit UI      │
│                      ───► Overlay       │
└─────────────────────────────────────────┘
```

---
**JARVIS learns and improves with use. The more you interact, the better it gets!**
