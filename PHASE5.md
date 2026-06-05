# Phase 5 Implementation Notes

Phase 5 adds the runtime foundations for:

- Windows Service support (`service/windows_service.py`)
- System tray launcher (`overlay/tray.py`)
- Dynamic plugin system (`backend/plugins/*`, `data/plugins/*`)
- GTX 1050 Ti / 4GB VRAM optimization profile (`backend/optimization/*`)
- Continuous voice conversation fixes (`backend/voice/integration.py`)
- Multi-agent debate safety gate (`backend/agent/debate.py`)

## Run Phase 5

```powershell
uv run python main.py --phase 5
```

Headless/service mode:

```powershell
uv run python main.py --phase 5 --headless
```

## Windows Service

Run PowerShell as Administrator:

```powershell
uv run python service/windows_service.py install
uv run python service/windows_service.py start
uv run python service/windows_service.py stop
uv run python service/windows_service.py remove
```

The service runs `main.py --phase 5 --headless`.

## System Tray

```powershell
uv run python -m overlay.tray
```

Tray menu: Start JARVIS, Stop JARVIS, Open Dashboard, Quit.

## Plugins

Plugins are Python files in either:

- `plugins/`
- `data/plugins/`

A plugin can expose `Plugin` class or a `plugin` object. Minimum shape:

```python
from backend.plugins.base import PluginResult

class Plugin:
    name = "example"
    description = "Example plugin"
    min_trust_level = 1

    def can_handle(self, command, context):
        return "example" in command.lower()

    async def handle(self, command, context):
        return PluginResult(True, True, "Handled by example", self.name)
```

## GTX 1050 Ti optimizations

The vision router now detects 4GB-class NVIDIA GPUs and:

- sets safer PyTorch CUDA allocation config
- lazy-loads vision models
- prefers SmolVLM/Florence-2
- skips Qwen by default on 4GB VRAM
- uses shorter generations to reduce VRAM pressure

## Multi-agent debate

High-impact commands such as install/delete/credential/send are passed through a debate gate before execution. If risk is high and trust is insufficient, JARVIS returns a warning and recommended plan instead of proceeding.
