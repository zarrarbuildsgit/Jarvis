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

## Sprint 2 Safety Gate

The action runtime now checks every structured action through `backend/security/policy.py` before execution.

Safety data is stored locally under `data/security/`:

- `approvals.json` — pending/resolved approval requests
- `audit.jsonl` — append-only action/policy audit events

API endpoints:

```text
GET  /api/approvals
POST /api/approvals/{approval_id}/approve
POST /api/approvals/{approval_id}/deny
GET  /api/audit?limit=100
```

Smoke checks:

```powershell
uv run python scripts/smoke_sprint2.py
uv run python scripts/smoke_sprint3.py
uv run python scripts/smoke_sprint4.py
uv run python scripts/smoke_sprint5.py
uv run python scripts/smoke_sprint6.py
uv run python scripts/smoke_sprint7.py
uv run python scripts/smoke_sprint8.py
uv run python scripts/smoke_sprint9.py
uv run python scripts/smoke_sprint10.py
uv run python scripts/smoke_sprint11.py
uv run python scripts/smoke_sprint12.py
uv run python scripts/run_quality_checks.py
```

## Sprint 3 Windows Automation Layer

The action runtime now has deterministic Windows-first helpers under `backend/windows/`:

- `apps.py` — friendly app-name aliases and app/URL launch support
- `windows.py` — list/focus/active-window helpers using pywinauto/win32gui when available
- `clipboard.py` — get/set clipboard text
- `processes.py` — list/find running processes
- `shell.py` — bounded shell/open helpers

New deterministic commands include:

```text
list windows
focus window Chrome
list processes
get clipboard
set clipboard to hello
paste clipboard
```

## Sprint 4 First-Party Plugins

The plugin pack now includes:

- `windows_apps` — open apps, list windows, focus windows
- `file_manager` — list/read/write files through policy checks
- `browser` — open URLs and web searches
- `system_monitor` — CPU/RAM/GPU/process status
- `audio_control` — media-key volume/mute controls where supported
- `terminal` — terminal command execution through policy checks
- `time` — basic local time/date plugin

Plugin metadata now includes `permissions` and `examples`, surfaced by `/api/plugins`.

## Sprint 5 Config Profiles

JARVIS now has a profile-aware config loader:

- `backend/config/schema.py` — typed dataclass schema
- `backend/config/loader.py` — YAML merge/profile loader
- `configs/default.yaml`
- `configs/gtx1050ti.yaml`
- `configs/low_ram.yaml`
- `configs/high_end_gpu.yaml`
- `configs/safe_mode.yaml`

Run with a profile:

```powershell
uv run python main.py --phase 5 --profile gtx1050ti
uv run python main.py --phase 5 --profile safe_mode
```

Config API endpoints:

```text
GET /api/config/profiles
GET /api/config?profile=gtx1050ti
```

The selected profile is passed into the main runtime and vision router. `gtx1050ti` forces the GTX 1050 Ti optimization profile and keeps heavy Qwen vision disabled by default.

## Sprint 6 Resource Guard + GTX 1050 Ti Hardening

JARVIS now includes resource monitoring and model pressure decisions:

- `backend/system/gpu_monitor.py` — CPU/RAM/GPU/VRAM telemetry via psutil, nvidia-smi, and torch fallback
- `backend/system/resource_guard.py` — pressure levels, recommended actions, and model-load decisions
- `backend/optimization/model_cache.py` — model lifecycle registry and idle unload callbacks

New API endpoint:

```text
GET /api/resources?profile=gtx1050ti
```

The vision router now checks the resource guard before loading models and exposes resource pressure/model-cache stats through `get_model_info()`. In GTX 1050 Ti, low-RAM, and safe-mode profiles, heavy models such as Qwen remain blocked by default.

## Sprint 7 Task Queue + Scheduler

JARVIS now has a persistent task queue and scheduler:

- `backend/tasks/models.py` — task/schedule dataclasses and statuses
- `backend/tasks/queue.py` — JSON-backed task queue with cancel/pause/resume/complete/fail
- `backend/tasks/scheduler.py` — one-time, delayed, interval, and daily schedule definitions
- `backend/tasks/history.py` — append-only task history JSONL

Task state is stored under `data/tasks/` at runtime.

Task API endpoints:

```text
POST   /api/agent/command
GET    /api/tasks?status=queued
GET    /api/tasks/history?limit=100
POST   /api/tasks/{task_id}/pause
POST   /api/tasks/{task_id}/resume
DELETE /api/tasks/{task_id}
```

Schedule API endpoints:

```text
POST   /api/schedules
GET    /api/schedules
POST   /api/schedules/enqueue-due
DELETE /api/schedules/{schedule_id}
```

The headless agent now sends a `running` update before processing queued tasks, and websocket task updates are mirrored back into the persistent queue.

## Sprint 8 Dashboard Control Center

The local dashboard is now operational through `ui-server/public/index.html` and the Svelte source dashboard in `frontend/src/routes/+page.svelte`.

Dashboard panels:

- Overview health/resources/trust
- Chat + quick command sender
- Persistent task queue controls
- Schedule creation/cancellation/enqueue-due
- Pending approvals with approve/deny buttons
- Plugin browser with permissions/examples
- Config profile viewer
- Memory/voice/status panel
- Audit log and task history

New/expanded backend endpoints:

```text
GET  /api/trust
POST /api/trust/level
GET  /api/memory/stats
```

The Express UI server now serves the standalone dashboard from `ui-server/public/` and falls back to `index.html` for local navigation.

## Sprint 9 Voice Conversation Upgrade

Voice mode now has a real conversation state layer:

- `backend/voice/conversation.py` — timed wake-word sessions, recent turns, follow-up context, session state
- `backend/voice/interrupts.py` — stop/cancel/pause/resume/sleep/status intent detection
- `backend/voice/audio_session.py` — playback state and barge-in stop helper
- `backend/voice/integration.py` — continuous follow-up context, interrupt handling, playback state callbacks

Supported voice control phrases include:

```text
stop
stop talking
cancel
never mind
pause listening
resume
go to sleep
voice status
```

Wake word starts a timed session. Follow-up commands inside the idle window are enriched with recent conversation context, so the agent can understand short follow-ups better. Playback can be stopped for barge-in style interruptions where supported by `sounddevice`.

## Sprint 10 Memory Intelligence

Memory now has deterministic ranking, preference extraction, retrieval context, and summarization:

- `backend/memory/scoring.py` — importance, recency, frequency, confidence, preference, and relevance scoring
- `backend/memory/preferences.py` — explicit user preference extraction and JSON-backed storage
- `backend/memory/retriever.py` — ranks Chroma-style memories and combines them with preference context
- `backend/memory/summarizer.py` — dependency-free memory/conversation summaries

New memory API endpoints:

```text
GET  /api/memory/preferences
POST /api/memory/preferences/ingest
GET  /api/memory/context?query=browser
```

`MemoryManager.add_episodic()` and `add_semantic()` now enrich metadata with memory scores. `JARVIS_Crew` ingests preferences from commands and builds relevant memory context before AI fallback planning.

## Sprint 11 Skill Learning / Macros

JARVIS can now save and run reusable workflows as skills:

- `backend/skills/skill_schema.py` — editable JSON skill/step schema based on Sprint 1 actions
- `backend/skills/skill_manager.py` — load/save/search/create skills under `data/skills/`
- `backend/skills/recorder.py` — record commands into reusable skills
- `backend/skills/runner.py` — execute skill steps through Sprint 2 policy/approval gates

Skill API endpoints:

```text
GET    /api/skills
POST   /api/skills
POST   /api/skills/{skill_id}/run
DELETE /api/skills/{skill_id}
```

`JARVIS_Crew` checks enabled skill trigger phrases before plugin/runtime fallback. A phrase like `start coding mode` can now run a saved macro. Skill execution still goes through policy checks, so destructive skill steps are blocked or require approval.

## Sprint 12 Browser Automation + External Integrations

Browser workflows now have deterministic helpers and safe draft-only integration behavior:

- `backend/browser/session.py` — open/search/read URL helpers and lightweight page text extraction
- `backend/browser/actions.py` — browser actions, page summarization, and external draft storage
- `backend/browser/__init__.py`
- `plugins/browser.py` — upgraded to use browser actions and draft external messages/emails

New browser/integration API endpoints:

```text
GET  /api/browser/drafts
POST /api/browser/read
POST /api/browser/draft
```

Supported browser plugin commands include:

```text
open url https://example.com
go to example.com
search web for jarvis ai
youtube search local ai
read url https://example.com
summarize url https://example.com
draft email to user@example.com saying hello
```

External communication is draft-only. JARVIS creates a draft record under `data/integrations/drafts.json` and does not send/post automatically.

## Sprint 13 Testing, CI, and Quality Gates

Quality gates are now in place:

- `tests/` — stdlib unit tests for planner, policy, memory, skills, browser, tasks, and config
- `scripts/run_quality_checks.py` — compile, unit test, smoke test, and Node syntax check runner
- `.github/workflows/ci.yml` — GitHub Actions workflow for pushes and pull requests

Run the full local quality suite:

```powershell
uv run python scripts/run_quality_checks.py
```

The quality runner executes all Sprint 2–12 smoke checks plus unit tests and compile checks.


