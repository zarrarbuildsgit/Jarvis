# JARVIS Improvement Sprints

This roadmap breaks the full JARVIS upgrade plan into quality-controlled sprints. Each sprint should be implemented, tested, reviewed, and committed separately to avoid rushed or hallucinated code.

## Guiding Rules

1. One sprint = one coherent set of architectural changes.
2. Every sprint must compile before commit.
3. Prefer deterministic Windows automation before AI/vision fallbacks.
4. Never add a risky action without policy + approval handling.
5. Keep GTX 1050 Ti mode as a first-class target.
6. Every new subsystem needs clear interfaces and docs.
7. Avoid huge rewrites unless a sprint explicitly targets refactoring.

---

# Sprint 1 — Core Action Engine

**Status: Implemented in local Sprint 1 commit.**

## Goal
Turn JARVIS from a planning skeleton into an assistant that can convert commands into executable, typed actions.

## Features
- Action schema
- Planner interface
- Deterministic planner for common commands
- Executor interface
- Basic observation model
- Action result model

## Files
- `backend/agent/action_schema.py`
- `backend/agent/planner.py`
- `backend/agent/executor.py`
- `backend/agent/observation.py`
- `backend/agent/runtime.py`

## Example Actions
- `open_app`
- `run_terminal`
- `type_text`
- `press_key`
- `click`
- `read_file`
- `write_file`
- `list_files`
- `analyze_screen`

## Acceptance Criteria
- Commands can be converted into structured actions. ✅
- Actions can execute through a single executor. ✅
- Results include success/failure, output, error, and metadata. ✅
- Existing plugin flow still works. ✅
- Python compilation passes. ✅

---

# Sprint 2 — Safety Policy + Approval System

**Status: Implemented in local Sprint 2 commit.**

## Goal
Make trust levels enforceable at the action level, not just command text level.

## Features
- Policy classifier
- Approval request model
- Audit log
- Block/allow/confirm decisions
- Trust level integration

## Files
- `backend/security/policy.py`
- `backend/security/approval.py`
- `backend/security/audit_log.py`
- `backend/security/rules.yaml`

## Acceptance Criteria
- Every action receives a safety decision. ✅
- Dangerous actions are blocked or require confirmation. ✅
- Audit log records all executed/blocked actions. ✅
- Delete/install/send/credential actions are guarded. ✅

---

# Sprint 3 — Windows Automation Layer

**Status: Implemented in local Sprint 3 commit.**

## Goal
Make Windows control reliable without depending on screen coordinates first.

## Features
- App launching
- Window listing/focus
- Clipboard operations
- Hotkeys
- Shell helpers
- Process helpers

## Files
- `backend/windows/apps.py`
- `backend/windows/windows.py`
- `backend/windows/clipboard.py`
- `backend/windows/shell.py`
- `backend/windows/processes.py`
- `backend/windows/__init__.py`

## Acceptance Criteria
- JARVIS can open Notepad/Chrome/VS Code by name. ✅
- JARVIS can focus windows by title. ✅
- Clipboard paste workflow works. ✅
- Coordinate clicking is fallback only. ✅

---

# Sprint 4 — First-Party Plugins Pack

**Status: Implemented in local Sprint 4 commit.**

## Goal
Add practical built-in skills using the plugin system.

## Plugins
- Windows app plugin
- File manager plugin
- Browser plugin
- System monitor plugin
- Volume/audio plugin
- Terminal plugin

## Files
- `plugins/windows_apps.py`
- `plugins/file_manager.py`
- `plugins/browser.py`
- `plugins/system_monitor.py`
- `plugins/audio_control.py`
- `plugins/terminal.py`

## Acceptance Criteria
- Plugins declare name, description, trust, permissions, examples. ✅
- Plugins use policy checks before risky actions. ✅
- `/api/plugins` shows useful metadata. ✅

---

# Sprint 5 — Config Profiles

## Goal
Centralize settings and support machine-specific profiles.

## Features
- Typed config schema
- Config loader
- Profile support
- CLI `--profile`
- Default/GTX1050Ti/low-RAM/high-end/safe-mode profiles

## Files
- `backend/config/schema.py`
- `backend/config/loader.py`
- `configs/default.yaml`
- `configs/gtx1050ti.yaml`
- `configs/low_ram.yaml`
- `configs/high_end_gpu.yaml`
- `configs/safe_mode.yaml`

## Acceptance Criteria
- App loads config through one path.
- `main.py --profile gtx1050ti` works.
- Existing `settings.yaml` remains compatible or is migrated.

---

# Sprint 6 — Resource Guard + GTX 1050 Ti Hardening

## Goal
Make low-VRAM operation safe and predictable.

## Features
- GPU/RAM monitor
- VRAM watchdog
- Model idle unload
- Memory pressure decisions
- Low-VRAM model routing

## Files
- `backend/system/gpu_monitor.py`
- `backend/system/resource_guard.py`
- `backend/optimization/model_cache.py`

## Acceptance Criteria
- JARVIS can report CPU/RAM/GPU/VRAM.
- Vision router respects resource pressure.
- Qwen stays disabled in GTX 1050 Ti profile unless explicitly enabled.

---

# Sprint 7 — Task Queue + Scheduler

## Goal
Support async tasks, delayed tasks, recurring jobs, and task history.

## Features
- Task model
- Queue worker
- Scheduler
- Task history
- Cancel/pause/resume

## Files
- `backend/tasks/models.py`
- `backend/tasks/queue.py`
- `backend/tasks/scheduler.py`
- `backend/tasks/history.py`
- `backend/tasks/__init__.py`

## Acceptance Criteria
- API-created tasks flow through queue.
- Tasks can be cancelled.
- Delayed and recurring task definitions exist.
- Task state survives restart where practical.

---

# Sprint 8 — Dashboard Control Center

## Goal
Make the dashboard operational, not just visual.

## Features
- Live task queue
- Plugin browser
- Trust controls
- Pending approvals
- Memory viewer
- System resource panel
- Voice status
- Logs panel

## Files
- `frontend/src/routes/+page.svelte`
- `backend/api.py`
- optional frontend components under `frontend/src/lib/`

## Acceptance Criteria
- User can approve/deny risky actions in UI.
- Dashboard shows real plugin/task/status data.
- WebSocket updates work.

---

# Sprint 9 — Voice Conversation Upgrade

## Goal
Make JARVIS feel conversational and interruptible.

## Features
- Conversation session state
- Follow-up context
- Interrupt commands
- Stop/cancel/pause handling
- Barge-in design

## Files
- `backend/voice/conversation.py`
- `backend/voice/audio_session.py`
- `backend/voice/interrupts.py`
- `backend/voice/integration.py`

## Acceptance Criteria
- Wake word starts a timed session.
- Follow-up commands do not need wake word.
- “stop/cancel/never mind” interrupts task flow.
- Voice status appears in API/dashboard.

---

# Sprint 10 — Memory Intelligence

## Goal
Make memory useful, ranked, and personalized.

## Features
- Importance scoring
- Recency/frequency scoring
- User preference extraction
- Memory confidence
- Memory summarization

## Files
- `backend/memory/scoring.py`
- `backend/memory/preferences.py`
- `backend/memory/retriever.py`
- `backend/memory/summarizer.py`

## Acceptance Criteria
- Memories have importance/confidence metadata.
- User preferences can be stored and retrieved.
- Agent runtime can query relevant memories before planning.

---

# Sprint 11 — Skill Learning / Macros

## Goal
Allow users to teach JARVIS reusable workflows.

## Features
- Skill schema
- Skill manager
- Skill recorder
- Skill runner
- Voice trigger support

## Files
- `backend/skills/skill_schema.py`
- `backend/skills/skill_manager.py`
- `backend/skills/recorder.py`
- `backend/skills/runner.py`
- `backend/skills/__init__.py`

## Acceptance Criteria
- User can save a named skill.
- Skill can run as a sequence of actions.
- Skills are stored as editable YAML/JSON.

---

# Sprint 12 — Browser Automation + External Integrations

## Goal
Add robust browser and online workflows safely.

## Features
- Browser session abstraction
- Open/search/read current page
- Draft-before-send for messages/emails
- Integration plugin pattern

## Files
- `backend/browser/session.py`
- `backend/browser/actions.py`
- `plugins/browser.py`
- future integration plugins

## Acceptance Criteria
- Browser actions use safe deterministic APIs where possible.
- Sending/posting actions require approval.
- Pages can be summarized/read into memory.

---

# Sprint 13 — Testing, CI, and Developer Quality Gates

## Goal
Prevent regressions and bad code quality.

## Features
- Unit tests for planner/executor/policy/plugins
- Mock screen/windows backends
- Ruff config cleanup
- Basic CI workflow

## Files
- `tests/`
- `.github/workflows/ci.yml`
- `pyproject.toml`

## Acceptance Criteria
- `python -m compileall` passes.
- Planner/policy/plugin tests pass.
- CI runs lint + tests.

---

# Recommended Implementation Order

1. Sprint 1 — Core Action Engine
2. Sprint 2 — Safety Policy + Approval System
3. Sprint 3 — Windows Automation Layer
4. Sprint 4 — First-Party Plugins Pack
5. Sprint 5 — Config Profiles
6. Sprint 6 — GTX 1050 Ti Hardening
7. Sprint 7 — Task Queue + Scheduler
8. Sprint 8 — Dashboard Control Center
9. Sprint 9 — Voice Conversation Upgrade
10. Sprint 10 — Memory Intelligence
11. Sprint 11 — Skill Learning / Macros
12. Sprint 12 — Browser Automation + External Integrations
13. Sprint 13 — Testing, CI, and Quality Gates

---

# Current Next Step

Sprints 1, 2, 3, and 4 are implemented. Next recommended sprint: **Sprint 5 — Config Profiles**. Do not begin dashboard, skills, or advanced voice work until profile-based config exists, because GTX 1050 Ti, safe mode, and high-end GPU behavior should be centralized before more systems depend on settings.
