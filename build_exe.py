"""
JARVIS PyInstaller Build Script
Compiles the Setup Wizard and Launcher into standalone .exe files.

Usage:
  uv run python build_exe.py

Output:
  dist/JARVIS_Setup.exe  - The installer wizard
  dist/JARVIS.exe        - The one-click launcher
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def install_pyinstaller():
    """Install PyInstaller if not present"""
    print("📦 Installing PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    print("✅ PyInstaller installed")

def build_setup_wizard():
    """Build JARVIS_Setup.exe"""
    print("\n🔨 Building JARVIS_Setup.exe...")
    
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "JARVIS_Setup",
        "--icon", "NONE",  # Add your .ico file here
        "--add-data", "backend/config/settings.yaml;backend/config",
        "--hidden-import", "customtkinter",
        "--hidden-import", "torch",
        "--hidden-import", "transformers",
        "--hidden-import", "chromadb",
        "--hidden-import", "crewai",
        "--hidden-import", "psutil",
        "--clean",
        "installer/wizard.py"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Build failed: {result.stderr}")
        return False
    
    print("✅ JARVIS_Setup.exe built successfully")
    return True

def build_launcher():
    """Build JARVIS.exe"""
    print("\n🔨 Building JARVIS.exe...")
    
    cmd = [
        "pyinstaller",
        "--onefile",
        "--name", "JARVIS",
        "--icon", "NONE",
        "--hidden-import", "customtkinter",
        "--hidden-import", "loguru",
        "--hidden-import", "crewai",
        "--hidden-import", "torch",
        "--hidden-import", "fastapi",
        "--hidden-import", "uvicorn",
        "--clean",
        "launcher.py"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Build failed: {result.stderr}")
        return False
    
    print("✅ JARVIS.exe built successfully")
    return True

def main():
    """Main build process"""
    print("=" * 50)
    print("🤖 JARVIS .exe Build Script")
    print("=" * 50)
    
    # Install PyInstaller
    install_pyinstaller()
    
    # Clean previous builds
    for dir_name in ["build", "dist", "__pycache__"]:
        if Path(dir_name).exists():
            shutil.rmtree(dir_name)
            print(f"🧹 Cleaned {dir_name}/")
    
    # Build both executables
    setup_ok = build_setup_wizard()
    launcher_ok = build_launcher()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Build Summary")
    print("=" * 50)
    
    if setup_ok:
        setup_path = Path("dist/JARVIS_Setup.exe")
        if setup_path.exists():
            size_mb = setup_path.stat().st_size / (1024 * 1024)
            print(f"✅ JARVIS_Setup.exe ({size_mb:.1f} MB)")
    
    if launcher_ok:
        launcher_path = Path("dist/JARVIS.exe")
        if launcher_path.exists():
            size_mb = launcher_path.stat().st_size / (1024 * 1024)
            print(f"✅ JARVIS.exe ({size_mb:.1f} MB)")
    
    print("\n📁 Executables are in the dist/ folder")
    print("🚀 Double-click JARVIS_Setup.exe to start the installer")
    print("=" * 50)

if __name__ == "__main__":
    main()
