@echo off
echo Starting Subway Surfers AI Body Controller...
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Running setup_env.bat first...
    call setup_env.bat
)
call .\venv\Scripts\python.exe main.py %*
pause
