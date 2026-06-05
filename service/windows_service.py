"""Windows Service wrapper for JARVIS Phase 5.

Usage (admin PowerShell):
  python service/windows_service.py install
  python service/windows_service.py start
  python service/windows_service.py stop
  python service/windows_service.py remove
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class _PortableServiceShim:
    """Non-Windows fallback so imports/tests do not fail on Linux/macOS."""
    _svc_name_ = "JarvisAI"
    _svc_display_name_ = "JARVIS AI Assistant"
    _svc_description_ = "Runs the local JARVIS agent, API, plugin manager, and voice loop."


def main() -> None:
    if sys.platform != "win32":
        print("Windows service management is only available on Windows.")
        return

    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    class JarvisWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = _PortableServiceShim._svc_name_
        _svc_display_name_ = _PortableServiceShim._svc_display_name_
        _svc_description_ = _PortableServiceShim._svc_description_

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.process: subprocess.Popen | None = None
            self.root = Path(__file__).resolve().parents[1]

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            if self.process and self.process.poll() is None:
                self.process.terminate()
            win32event.SetEvent(self.stop_event)

        def SvcDoRun(self):
            servicemanager.LogInfoMsg("Starting JARVIS service")
            python = sys.executable
            env = os.environ.copy()
            env.setdefault("JARVIS_SERVICE", "1")
            self.process = subprocess.Popen(
                [python, "main.py", "--phase", "5", "--headless"],
                cwd=str(self.root),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
            servicemanager.LogInfoMsg("JARVIS service stopped")

    win32serviceutil.HandleCommandLine(JarvisWindowsService)


if __name__ == "__main__":
    main()
