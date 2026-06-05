@echo off
echo ========================================
echo    J.A.R.V.I.S. - Starting System
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check UV
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: UV package manager is not installed
    echo Install: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

REM Setup venv if needed
if not exist ".venv" (
    echo Creating virtual environment...
    uv venv
    echo Installing dependencies...
    uv sync
)

REM Create data directories
if not exist "data\memory" mkdir "data\memory"
if not exist "data\logs" mkdir "data\logs"
if not exist "data\voice_samples" mkdir "data\voice_samples"
if not exist "data\voice_output" mkdir "data\voice_output"
if not exist "data\screenshots" mkdir "data\screenshots"

echo.
echo Starting JARVIS Phase 1...
echo.

REM Start the agent
uv run python main.py --phase 1

pause
