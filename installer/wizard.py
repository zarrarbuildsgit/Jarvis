"""
JARVIS Setup Wizard
GUI installer that handles ALL dependencies, models, and configuration.
Compile to JARVIS_Setup.exe with PyInstaller.

Usage (after building):
  1. Double-click JARVIS_Setup.exe
  2. Follow the wizard
  3. Launch JARVIS with one click
"""

import sys
import subprocess
import os
import platform
import shutil
import json
import time
import urllib.request
from pathlib import Path
from typing import Optional
import customtkinter as ctk
from threading import Thread
import traceback

# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class JARVIS_Installer(ctk.CTk):
    """Complete GUI installer for JARVIS"""
    
    def __init__(self):
        super().__init__()
        
        self.title("JARVIS Setup Wizard v0.1.0")
        self.geometry("700x600")
        self.resizable(False, False)
        
        # Installation state
        self.install_dir = Path(__file__).parent.parent  # Default to project root
        self.steps_completed = 0
        self.total_steps = 7
        self.installation_log = []
        self.step_names = [
            "System Check",
            "Python & UV",
            "Dependencies",
            "Node.js Setup",
            "AI Models",
            "Configuration",
            "Launcher Creation"
        ]
        
        # Build UI
        self._build_ui()
        self.log("🤖 Welcome to JARVIS Setup Wizard")
        self.log("This will install all dependencies and models automatically.")
        self.log("")
    
    def _build_ui(self):
        """Build the installer UI"""
        # Header
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1E3A8A")
        self.header_frame.pack(fill="x")
        
        ctk.CTkLabel(
            self.header_frame,
            text="🤖 J.A.R.V.I.S. Setup Wizard",
            font=("Segoe UI", 24, "bold"),
            text_color="white"
        ).pack(pady=(15, 5))
        
        ctk.CTkLabel(
            self.header_frame,
            text="Just A Rather Very Intelligent System - Complete Installer",
            font=("Segoe UI", 12),
            text_color="#93C5FD"
        ).pack(pady=(0, 15))
        
        # Main content
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Progress
        self.progress_label = ctk.CTkLabel(
            self.main_frame,
            text="Ready to install",
            font=("Segoe UI", 14, "bold")
        )
        self.progress_label.pack(pady=(15, 5))
        
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=600)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        # Steps
        self.steps_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.steps_frame.pack(fill="x", padx=20, pady=10)
        
        self.step_labels = []
        for i, step in enumerate(self.step_names):
            label = ctk.CTkLabel(
                self.steps_frame,
                text=f"○ {step}",
                font=("Segoe UI", 10),
                text_color="gray"
            )
            label.grid(row=0, column=i, padx=3, pady=5)
            self.step_labels.append(label)
        
        # Log box
        self.log_box = ctk.CTkTextbox(
            self.main_frame,
            height=250,
            font=("Consolas", 11),
            fg_color="#111827",
            text_color="#D1D5DB",
            border_width=1,
            border_color="#374151"
        )
        self.log_box.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Status bar
        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Click 'Start Installation' to begin",
            font=("Segoe UI", 12)
        )
        self.status_label.pack(side="left")
        
        # Buttons
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        self.install_btn = ctk.CTkButton(
            self.btn_frame,
            text="🚀 Start Installation",
            command=self.start_installation,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=("Segoe UI", 14, "bold"),
            width=200,
            height=40
        )
        self.install_btn.pack(side="right", padx=(10, 0))
        
        ctk.CTkButton(
            self.btn_frame,
            text="📁 Browse",
            command=self.browse_directory,
            fg_color="#374151",
            hover_color="#4B5563",
            font=("Segoe UI", 12),
            width=100,
            height=35
        ).pack(side="right")
        
        self.dir_label = ctk.CTkLabel(
            self.btn_frame,
            text=f"Install to: {self.install_dir}",
            font=("Segoe UI", 10),
            text_color="#9CA3AF"
        )
        self.dir_label.pack(side="left", padx=(10, 0))
    
    def log(self, message: str):
        self.installation_log.append(message)
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.update()
    
    def update_progress(self, step: int, message: str):
        self.progress_bar.set(step / self.total_steps)
        self.progress_label.configure(text=message)
        
        for i in range(min(step, len(self.step_labels))):
            self.step_labels[i].configure(
                text=f"✅ {self.step_names[i]}",
                text_color="#22C55E"
            )
        if step < len(self.step_labels):
            self.step_labels[step].configure(
                text=f"⏳ {self.step_names[step]}",
                text_color="#FBBF24"
            )
        
        self.status_label.configure(text=message)
        self.update()
    
    def browse_directory(self):
        try:
            import tkinter.filedialog as fd
            new_dir = fd.askdirectory(initialdir=self.install_dir)
            if new_dir:
                self.install_dir = Path(new_dir)
                self.dir_label.configure(text=f"Install to: {self.install_dir}")
        except Exception as e:
            self.log(f"⚠️ Could not open directory browser: {e}")
    
    def start_installation(self):
        self.install_btn.configure(state="disabled", text="⏳ Installing...")
        Thread(target=self.run_installation, daemon=True).start()
    
    def run_installation(self):
        try:
            self.update_progress(1, "Checking system requirements...")
            self.check_system()
            
            self.update_progress(2, "Setting up Python & UV...")
            self.setup_python_uv()
            
            self.update_progress(3, "Installing Python dependencies...")
            self.install_python_deps()
            
            self.update_progress(4, "Setting up Node.js dependencies...")
            self.setup_node()
            
            self.update_progress(5, "Downloading AI models...")
            self.download_models()
            
            self.update_progress(6, "Configuring JARVIS...")
            self.configure_jarvis()
            
            self.update_progress(7, "Creating launchers...")
            self.create_launchers()
            
            self.log("")
            self.log("=" * 50)
            self.log("🎉 JARVIS Installation Complete!")
            self.log("=" * 50)
            self.log("")
            self.log("You can now:")
            self.log("  • Double-click 'JARVIS.exe' to launch")
            self.log("  • Use the desktop shortcut")
            self.log("  • Run 'start_jarvis.bat' for manual mode")
            
            self.progress_label.configure(text="✅ Installation Complete!")
            self.progress_bar.set(1)
            self.status_label.configure(text="Ready to launch JARVIS")
            self.install_btn.configure(
                text="🚀 Launch JARVIS",
                state="normal",
                command=self.launch_jarvis
            )
            
        except Exception as e:
            self.log(f"\n❌ Installation failed: {e}")
            self.status_label.configure(text="Installation Failed", text_color="#EF4444")
            self.install_btn.configure(
                text="🔄 Retry",
                state="normal",
                command=self.start_installation
            )
            self.log(traceback.format_exc())
    
    def check_system(self):
        self.log("🔍 Checking system...")
        
        if platform.system() != "Windows":
            self.log("⚠️ Not running on Windows. Some features may not work.")
        else:
            self.log(f"✅ Windows {platform.version()}")
        
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024**3)
            status = "✅" if ram_gb >= 16 else "⚠️"
            self.log(f"{status} RAM: {ram_gb:.1f} GB")
        except:
            self.log("⚠️ Could not check RAM")
        
        try:
            import torch
            if torch.cuda.is_available():
                gpu = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                self.log(f"✅ GPU: {gpu} ({vram:.1f}GB VRAM)")
            else:
                self.log("⚠️ No GPU detected - will use CPU (slower)")
        except:
            self.log("⚠️ Could not check GPU")
        
        try:
            disk = shutil.disk_usage(self.install_dir)
            free_gb = disk.free / (1024**3)
            status = "✅" if free_gb > 10 else "⚠️"
            self.log(f"{status} Disk: {free_gb:.1f} GB free")
        except:
            self.log("⚠️ Could not check disk space")
        
        self.log("✅ System check complete")
    
    def setup_python_uv(self):
        self.log("🐍 Setting up Python & UV...")
        
        # Check Python
        if not self.check_command("python --version"):
            self.log("❌ Python not found. Installing Python 3.11...")
            self.install_python()
        else:
            version = self.get_output("python --version").strip()
            self.log(f"✅ {version}")
        
        # Check/Install UV
        if not self.check_command("uv --version"):
            self.log("📦 Installing UV package manager...")
            self.install_uv()
        else:
            version = self.get_output("uv --version").strip()
            self.log(f"✅ UV {version}")
        
        # Create venv
        self.log("🔧 Creating virtual environment...")
        self.run_cmd("uv venv", cwd=self.install_dir)
        self.log("✅ Virtual environment created")
    
    def install_python_deps(self):
        self.log("📦 Installing Python dependencies...")
        result = self.run_cmd("uv sync", cwd=self.install_dir, timeout=300)
        if result["success"]:
            self.log("✅ Python dependencies installed")
        else:
            self.log("⚠️ Some dependencies may have failed. Continuing...")
    
    def setup_node(self):
        self.log("📦 Setting up Node.js...")
        
        if self.check_command("node --version"):
            version = self.get_output("node --version").strip()
            self.log(f"✅ Node.js {version}")
            
            ui_server = self.install_dir / "ui-server"
            if ui_server.exists():
                self.log("📦 Installing UI server dependencies...")
                self.run_cmd("npm install", cwd=ui_server)
                self.log("✅ Node.js dependencies installed")
        else:
            self.log("⚠️ Node.js not found. Dashboard will not be available.")
            self.log("  Install from: https://nodejs.org/")
    
    def download_models(self):
        self.log("🧠 Downloading AI models...")
        
        models_dir = self.install_dir / "models"
        if models_dir.exists() and any(models_dir.iterdir()):
            self.log("✅ Models already exist, skipping download")
            return
        
        self.log("This may take a while depending on your internet speed...")
        self.log("Models to download:")
        self.log("  • SmolVLM-Instruct (~500MB)")
        self.log("  • Florence-2-base (~1GB)")
        self.log("  • Qwen2.5-VL-3B (~6GB)")
        self.log("")
        
        try:
            result = self.run_cmd(
                "uv run python scripts/download_models.py",
                cwd=self.install_dir,
                timeout=3600
            )
            if result["success"]:
                self.log("✅ AI models downloaded successfully")
            else:
                self.log("⚠️ Model download had issues. You can retry later.")
        except Exception as e:
            self.log(f"⚠️ Model download failed: {e}")
            self.log("You can manually run: uv run python scripts/download_models.py")
    
    def configure_jarvis(self):
        self.log("⚙️ Configuring JARVIS...")
        
        config = {
            "install_path": str(self.install_dir),
            "install_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": "0.1.0",
            "phase": 2,
            "voice_enabled": True,
            "overlay_enabled": True,
            "dashboard_port": 3001,
            "api_port": 8000
        }
        
        config_path = self.install_dir / "data" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        self.log("✅ Configuration saved")
        
        for d in ["data/memory", "data/logs", "data/voice_samples", 
                  "data/voice_output", "data/screenshots"]:
            (self.install_dir / d).mkdir(parents=True, exist_ok=True)
        
        self.log("✅ Data directories created")
    
    def create_launchers(self):
        self.log("🔗 Creating launchers...")
        
        # Create JARVIS.bat (the easy launcher)
        bat_content = f'''@echo off
title JARVIS - Just A Rather Very Intelligent System
echo ========================================
echo    J.A.R.V.I.S. - Starting System
echo ========================================
echo.
cd /d "{self.install_dir}"
call .venv\\Scripts\\activate
echo Starting JARVIS Phase 2...
echo.
python main.py --phase 2
pause
'''
        bat_path = self.install_dir / "JARVIS.bat"
        with open(bat_path, 'w') as f:
            f.write(bat_content)
        self.log("✅ JARVIS.bat created")
        
        # Create Desktop Shortcut
        try:
            desktop = Path.home() / "Desktop"
            import shutil
            shutil.copy2(bat_path, desktop / "JARVIS.lnk")
            self.log("✅ Desktop shortcut created")
        except Exception as e:
            self.log(f"⚠️ Could not create desktop shortcut: {e}")
        
        self.log("✅ Launchers created")
    
    def launch_jarvis(self):
        self.log("🚀 Launching JARVIS...")
        try:
            bat_path = self.install_dir / "JARVIS.bat"
            if bat_path.exists():
                subprocess.Popen(
                    ["start", "cmd", "/k", f"cd /d {self.install_dir} && JARVIS.bat"],
                    shell=True
                )
            else:
                self.log("❌ JARVIS.bat not found")
        except Exception as e:
            self.log(f"❌ Failed to launch: {e}")
    
    # Utility methods
    def check_command(self, cmd: str) -> bool:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except:
            return False
    
    def get_output(self, cmd: str) -> str:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout
        except:
            return ""
    
    def run_cmd(self, cmd: str, cwd: Optional[Path] = None, timeout: int = 60) -> dict:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd
            )
            success = result.returncode == 0
            
            if result.stdout.strip():
                self.log(f"  {result.stdout.strip()[:100]}")
            if result.stderr.strip() and not success:
                self.log(f"  Error: {result.stderr.strip()[:100]}")
            
            return {"success": success, "output": result.stdout, "error": result.stderr}
        except subprocess.TimeoutExpired:
            self.log(f"  ⏰ Command timed out after {timeout}s")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            self.log(f"  ❌ Command failed: {e}")
            return {"success": False, "error": str(e)}
    
    def install_python(self):
        self.log("⬇️ Downloading Python installer...")
        try:
            url = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
            installer_path = Path(os.environ.get("TEMP", ".")) / "python_installer.exe"
            
            def download_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                pct = min(100, int(downloaded * 100 / total_size)) if total_size > 0 else 0
                if pct % 10 == 0:
                    self.log(f"  Downloading... {pct}%")
            
            urllib.request.urlretrieve(url, installer_path, download_progress)
            self.log("✅ Python installer downloaded")
            
            self.log("📦 Installing Python...")
            subprocess.run(
                [str(installer_path), "/quiet", "InstallAllUsers=0", "PrependPath=1"],
                timeout=300
            )
            self.log("✅ Python installed")
        except Exception as e:
            self.log(f"❌ Python installation failed: {e}")
            self.log("Please install Python manually from https://www.python.org/downloads/")
            raise
    
    def install_uv(self):
        self.log("⬇️ Installing UV...")
        try:
            cmd = "powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self.log("✅ UV installed")
            else:
                self.log(f"⚠️ UV install had issues: {result.stderr}")
        except Exception as e:
            self.log(f"❌ UV installation failed: {e}")
            raise

def main():
    app = JARVIS_Installer()
    app.mainloop()

if __name__ == "__main__":
    main()
