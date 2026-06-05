"""
JARVIS Launcher
One-click boot: Agent + API + Dashboard + Overlay
Compile to JARVIS.exe with PyInstaller
"""

import sys
import os
import subprocess
import threading
import time
import signal
from pathlib import Path
from loguru import logger
import customtkinter as ctk

class JARVIS_Launcher:
    """Boots all JARVIS components with one click"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.processes = {}
        self.running = False
        
        # Components to start
        self.components = {
            "api": {
                "cmd": ["python", "-m", "uvicorn", "backend.api:app", "--host", "127.0.0.1", "--port", "8000"],
                "name": "FastAPI Backend",
                "port": 8000
            },
            "agent": {
                "cmd": ["python", "main.py", "--phase", "5", "--headless"],
                "name": "JARVIS Agent",
                "port": None
            },
            "ui": {
                "cmd": ["npm", "run", "dev", "--prefix", "ui-server"],
                "name": "Dashboard Server",
                "port": 3001
            },
            "overlay": {
                "cmd": ["python", "-m", "overlay.tray"],
                "name": "Desktop Overlay",
                "port": None
            }
        }
    
    def start(self):
        """Start all JARVIS components"""
        self.running = True
        logger.info("🚀 JARVIS Launcher starting...")
        
        # Start each component in a separate thread
        for key, config in self.components.items():
            thread = threading.Thread(
                target=self._start_component,
                args=(key, config),
                daemon=True
            )
            thread.start()
            time.sleep(1)  # Stagger starts
        
        # Show status window
        self._show_status_window()
    
    def _start_component(self, key: str, config: dict):
        """Start a single component"""
        name = config["name"]
        cmd = config["cmd"]
        
        logger.info(f"📦 Starting {name}...")
        
        try:
            # Set working directory
            cwd = self.base_dir
            
            # Create process
            process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            
            self.processes[key] = process
            logger.info(f"✅ {name} started (PID: {process.pid})")
            
            # Monitor process
            process.wait()
            logger.warning(f"⚠️ {name} exited with code {process.returncode}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start {name}: {e}")
    
    def _show_status_window(self):
        """Show a simple status window"""
        try:
            root = ctk.CTk()
            root.title("JARVIS Status")
            root.geometry("300x200")
            root.attributes("-topmost", True)
            
            ctk.CTkLabel(root, text="🤖 JARVIS Running", font=("Segoe UI", 18, "bold")).pack(pady=20)
            
            for key, config in self.components.items():
                status = "✅" if key in self.processes else "⏳"
                ctk.CTkLabel(root, text=f"{status} {config['name']}").pack(pady=2)
            
            ctk.CTkButton(root, text="Stop JARVIS", command=self.stop, fg_color="#EF4444").pack(pady=20)
            
            root.protocol("WM_DELETE_WINDOW", self.stop)
            root.mainloop()
            
        except Exception as e:
            logger.warning(f"Status window failed: {e}")
            # Keep running without UI
            while self.running:
                time.sleep(1)
    
    def stop(self):
        """Stop all JARVIS components"""
        logger.info("🛑 Stopping JARVIS...")
        self.running = False
        
        for key, process in self.processes.items():
            try:
                if process.poll() is None:  # Still running
                    process.terminate()
                    logger.info(f"🛑 Stopped {self.components[key]['name']}")
            except Exception as e:
                logger.error(f"Failed to stop {key}: {e}")
        
        sys.exit(0)

def main():
    """Launcher entry point"""
    launcher = JARVIS_Launcher()
    
    # Handle shutdown signals
    signal.signal(signal.SIGINT, lambda s, f: launcher.stop())
    signal.signal(signal.SIGTERM, lambda s, f: launcher.stop())
    
    launcher.start()

if __name__ == "__main__":
    main()
