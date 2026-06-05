"""System tray controller for JARVIS Phase 5."""
from __future__ import annotations

import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from loguru import logger


class JarvisTray:
    def __init__(self):
        self.root = Path(__file__).resolve().parents[1]
        self.process: subprocess.Popen | None = None
        self.icon = None

    def start_jarvis(self):
        if self.process and self.process.poll() is None:
            return
        self.process = subprocess.Popen([sys.executable, "main.py", "--phase", "5", "--headless"], cwd=self.root)
        logger.info("Started JARVIS from tray")

    def stop_jarvis(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            logger.info("Stopped JARVIS from tray")

    def open_dashboard(self):
        webbrowser.open("http://127.0.0.1:3001")

    def run(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception as exc:
            logger.error("pystray/Pillow unavailable: %s", exc)
            return

        image = Image.new("RGB", (64, 64), "#111827")
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill="#2563EB")
        draw.text((24, 22), "J", fill="white")

        def on_start(icon, item): self.start_jarvis()
        def on_stop(icon, item): self.stop_jarvis()
        def on_dashboard(icon, item): self.open_dashboard()
        def on_quit(icon, item):
            self.stop_jarvis()
            icon.stop()

        self.icon = pystray.Icon(
            "JARVIS",
            image,
            "JARVIS",
            menu=pystray.Menu(
                pystray.MenuItem("Start JARVIS", on_start),
                pystray.MenuItem("Stop JARVIS", on_stop),
                pystray.MenuItem("Open Dashboard", on_dashboard),
                pystray.MenuItem("Quit", on_quit),
            ),
        )
        threading.Thread(target=self.start_jarvis, daemon=True).start()
        self.icon.run()


def main():
    JarvisTray().run()


if __name__ == "__main__":
    main()
