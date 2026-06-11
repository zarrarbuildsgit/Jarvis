# Hermes Layer Hardening Report

**Date:** June 11, 2026
**Scope:** Multi-agent review + test pass over the uncommitted Hermes sprints (2–6) and shared runtime files.
**Result:** Test suite 11 → **100 passing**. Backend compiles clean. ~30 real bugs fixed.

---

## Blocking issue fixed first

The working tree contained **unresolved merge conflict markers** (`<<<<<<< HEAD`) in `backend/api.py`, `backend/agent/trajectory.py`, and `backend/skills/curator.py`. The backend could not be imported at all. Resolved (HEAD side kept in all cases).

## Security fixes (Telegram gateway)

- **CRITICAL — allowlist failed open.** An empty `allowed_users` list (the API's default) allowed *any* Telegram user to message the agent. Now fail-closed in `telegram.py`, and `POST /api/gateway/telegram/setup` rejects empty allowlists.
- **HIGH — allowlist type mismatch.** Telegram int user IDs never matched stored strings; IDs normalized at every entry point.
- Token never logged or returned by any endpoint (`has_token` only); `drop_pending_updates=True` prevents replay of pre-configuration commands.

## Correctness fixes by subsystem

**Gateway (`backend/gateway/*`):** config round-trip loss on restart; loaded gateways missing message handlers; silent polling-task death (invalid token reported success); broken partial teardown leaking connections; non-idempotent start; atomic config writes. **api.py:** gateway endpoints now share one manager instance (stop previously operated on a *different* object than the running poller — gateways were unstoppable), and configured gateways auto-start/stop with the app.

**Skill learning (`backend/skills/*`, `backend/agent/trajectory.py`):** naive/aware timezone mixing that shifted the curator's lookback window and silently broke recency scoring; `get_stats` sampling unsorted files and deflating success-rate metrics; skill-improvement ID collisions at second resolution; silent wipe of a skill's performance history on unknown JSON keys; crashes on empty patterns/names; atomic writes for suggestions and performance files. **runner.py:** optional-step failures no longer fail the whole skill; failure reasons are recorded even when `error` is None. **runtime.py:** loguru printf-style bug dropping log args; misleading exception labeling; bare except swallow.

**Scheduling (`backend/tasks/*`):** "every monday at 9am" silently became a one-shot; invalid times (hour 25, minute 75) crashed `compute_next_run` later; **daily schedules computed next-run in UTC, not local time** ("9am" fired at 2pm in UTC+5) — fixed in `models.py`; added a real `WEEKLY` schedule type (`models.py`, `scheduler.py`, `/api/schedules`); noon/midnight support; "every evening at 8" now means 8 PM.

**Memory nudges (`backend/memory/nudges.py`):** extracted preferences were never actually persisted (pattern mismatch dropped 100%); substring false positives ("decode" matched "code"); MEMORY.md grew without bound — now hard-capped at 16 KB with history-section dedup.

## Test files added

- `tests/test_hermes_skill_learning.py` (28), `tests/test_hermes_nudges_nlparser.py` (35), `tests/test_hermes_gateway.py` (21), `tests/test_schedule_weekly.py` (5). All offline — no GPU, models, or network.

## Known remaining issues (deliberate, documented)

1. **No bridge from gateway → agent runtime.** Telegram messages are received, allowlist-checked, logged — and dropped. The bridge is Sprint 6's remaining work; when built, remote commands MUST route through `backend/security/policy.py` with no auto-approval for remote origins.
2. **Bot token stored in plaintext** at `data/gateway/config.json`. Move to Windows DPAPI/`keyring` (roadmap P0).
3. **"Every weekday at 8am" runs on weekends** — parser emits cron `1-5` but scheduler has no day-filter; needs a WEEKDAYS type or cron support.
4. `TrajectoryLogger` holds one mutable current trajectory — concurrent commands on the same runtime would interleave traces.
5. Skill executions don't produce trajectories, so they're invisible to the curator's pattern detection.
6. Individual `traj_*.json` files accumulate without cleanup.
7. All data paths are CWD-relative; server must launch from repo root (components are now parameterizable when this gets fixed).

See `03_market_readiness_roadmap.md` for the full path to launch.
