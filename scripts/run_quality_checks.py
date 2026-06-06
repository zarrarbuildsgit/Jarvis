"""Run JARVIS quality gates locally/CI.

This intentionally uses mostly stdlib tooling so the suite can run in minimal
agent environments. Heavy Windows/GPU/audio behavior is covered by smoke tests
that use fakes and portable fallbacks.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

SMOKE_SCRIPTS = [
    "scripts/smoke_sprint2.py",
    "scripts/smoke_sprint3.py",
    "scripts/smoke_sprint4.py",
    "scripts/smoke_sprint5.py",
    "scripts/smoke_sprint6.py",
    "scripts/smoke_sprint7.py",
    "scripts/smoke_sprint8.py",
    "scripts/smoke_sprint9.py",
    "scripts/smoke_sprint10.py",
    "scripts/smoke_sprint11.py",
    "scripts/smoke_sprint12.py",
]


def run(cmd: list[str], label: str) -> None:
    print(f"\n==> {label}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def main() -> None:
    run([sys.executable, "-m", "compileall", "-q", "backend", "plugins", "scripts", "main.py"], "Python compile")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"], "Unit tests")
    for smoke in SMOKE_SCRIPTS:
        run([sys.executable, smoke], smoke)
    if shutil.which("node"):
        run(["node", "--check", "ui-server/src/server.mjs"], "Node syntax")
    else:
        print("\n==> Node not installed; skipping ui-server syntax check")
    print("\n✅ All JARVIS quality checks passed")


if __name__ == "__main__":
    main()
