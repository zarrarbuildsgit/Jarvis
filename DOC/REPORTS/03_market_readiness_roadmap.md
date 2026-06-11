# JARVIS Market-Readiness Roadmap

**Date:** June 11, 2026
**Status:** Working draft — grounded in a code audit of the repo as of this date
**Scope:** What separates the current codebase from a product a stranger can install, trust, and pay for.

---

## Where the codebase actually is

- **Core platform (Sprints 1–13): committed and green.** Action engine, safety policy + approval, Windows automation, plugins, config profiles, resource guard, task queue/scheduler, dashboard, voice, memory, skill macros, browser automation, quality gates. 11/11 tests pass.
- **Hermes self-improvement layer (Sprints 1–6 of the new plan): code written, now compiling.** Trajectory logging, skill curator, autonomous creator, skill improver, memory nudges, NL cron parsing, Telegram gateway — all wired into `backend/api.py`. As of June 11 the working tree contained unresolved merge conflict markers that made the backend unimportable; those are fixed. Test coverage for this layer is being added (see hardening pass).
- **Packaging: started, unverified.** `build_exe.py` (PyInstaller) and `installer/wizard.py` exist but there is no evidence of a recent successful build artifact or a signed binary.

**Honest grade: strong beta engine, pre-alpha product.** The differentiator (local + self-improving + desktop control) is real and built. What's missing is everything around it.

---

## P0 — Cannot ship without these

| # | Gap | Why it blocks shipping | Concrete next step |
|---|-----|------------------------|--------------------|
| 1 | **Test coverage on the learning layer** | 2,000+ new lines with zero tests; this layer writes files, schedules tasks, and creates skills autonomously | In progress: `tests/test_hermes_*.py` (skill learning, nudges/NL parser, gateway) |
| 2 | **Telegram gateway security** | Remote channel into a PC-control agent. Token storage, allowlist enforcement, and policy-system pass-through must be verified, not assumed | Security review in progress; encrypt token at rest (Windows DPAPI via `keyring`), enforce allowlist on every update, route all remote commands through `backend/security/policy.py` |
| 3 | **One-command verified install** | `uv sync` + npm + 5–10 GB model download + GPU detection is a developer flow, not a customer flow | Make `build_exe.py` produce a working `JARVIS_Setup.exe`; wizard must handle: no GPU, low VRAM (1050 Ti profile), disk-space check, resumable model download |
| 4 | **Crash containment + diagnostics** | An autonomous agent that dies silently or half-executes an action destroys trust instantly | Global exception handler → local crash log + user-visible "JARVIS hit a problem" surface; never a silent hang. (Local-only logs — no telemetry without opt-in, it's the product's core promise) |
| 5 | **First-run experience** | First 10 minutes decide refunds | Wizard → voice test → screen-permission walkthrough → one guaranteed-success demo task ("Open Notepad and type hello") |

## P1 — Needed within weeks of launch

1. **Auto-updater.** Shipping a local agent with no update channel means shipping bugs forever. Simplest viable: signed delta updates checked on launch, user-approved.
2. **Code signing + SmartScreen reputation.** Unsigned PyInstaller exes that capture the screen and control input will be flagged by Defender/SmartScreen. Budget for an EV cert and AV vendor whitelisting lead time (weeks).
3. **Model licensing audit.** Qwen2.5-VL (Apache-2.0), Florence-2 (MIT), F5-TTS (check weights license — CC-BY-NC variants exist), Canary (NVIDIA license — likely NOT redistributable commercially). A commercial product must either swap restricted models or download them user-side under user acceptance.
4. **Resource envelope honesty.** Define and test minimum spec (the 1050 Ti profile is the floor — verify it end-to-end on real hardware) and a CPU-only degraded mode that fails gracefully.
5. **Docs split: user vs developer.** README is developer-facing. Need a non-technical quickstart, a safety/trust-levels explainer, and a "what JARVIS will never do" page.

## P2 — Market positioning

1. **Pricing/licensing decision.** Local-first suggests one-time license + paid major upgrades, or free core + paid Hermes learning layer. Avoid subscriptions that imply a cloud you don't run.
2. **Distribution.** Direct download + winget manifest first; Microsoft Store later (the input-control APIs may face store policy friction).
3. **Demo assets.** This product demos spectacularly (voice → screen action → self-created skill). 90-second video is the single highest-ROI marketing artifact.
4. **Support loop.** A GitHub Discussions or Discord channel and an in-app "export diagnostic bundle" button.

---

## Suggested sequence (realistic, solo-friendly)

1. **Now:** Hermes hardening pass (tests + security + bug fixes) → commit Sprints 2–6 cleanly.
2. **Next 1–2 weeks:** Hermes Sprints 7–8 (subagent delegation, polish) per `DOC/REPORTS/01_agile_sprint_plan.md`.
3. **Weeks 3–4:** P0 items 3–5 (installer, crash containment, first-run).
4. **Weeks 5–6:** P1 items 1–3 (updater, signing, license audit) → **closed beta with 5–10 real users.**
5. **Beta feedback loop ≥ 2 weeks**, then public launch.

The fastest credible path to "market ready" is roughly **8–10 weeks** from today — not because the AI is unfinished, but because installers, signing, licensing, and beta feedback can't be compressed.
