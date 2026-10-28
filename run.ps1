# Quick Launcher for PowerShell
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    Write-Host "[INFO] Virtual environment not found. Running setup_env.ps1..." -ForegroundColor Yellow
    & .\setup_env.ps1
}
& .\venv\Scripts\python.exe main.py $args
