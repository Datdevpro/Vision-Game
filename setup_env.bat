@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo    SUBWAY SURFERS AI BODY CONTROLLER - SETUP SCRIPT
echo ========================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH! Please install Python 3.11 or 3.12.
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Setting up Python virtual environment (venv)...
if not exist "venv\Scripts\python.exe" (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created in .\venv
) else (
    echo Existing virtual environment found in .\venv
)

echo.
echo [3/4] Installing required dependencies...
call .\venv\Scripts\python.exe -m pip install --upgrade pip
call .\venv\Scripts\pip.exe install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation encountered an issue!
    pause
    exit /b 1
)

echo.
echo [4/4] Downloading official MediaPipe Pose Landmarker models...
call .\venv\Scripts\python.exe download_models.py
if %errorlevel% neq 0 (
    echo [ERROR] Model download failed!
    pause
    exit /b 1
)

echo.
echo ========================================================
echo    SETUP COMPLETE! YOU ARE READY TO PLAY!
echo ========================================================
echo To launch the application, run:
echo    run.bat
echo or:
echo    .\venv\Scripts\python main.py
echo.
pause
