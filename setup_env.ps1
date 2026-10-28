# Subway Surfers AI Body Controller - PowerShell Setup Script
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   SUBWAY SURFERS AI BODY CONTROLLER - SETUP SCRIPT" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Host "[ERROR] Python was not found in your PATH! Please install Python 3.11 or 3.12." -ForegroundColor Red
    Exit 1
}

Write-Host "[1/4] Checking Python version..." -ForegroundColor Yellow
& python --version

Write-Host ""
Write-Host "[2/4] Setting up Python virtual environment (venv)..." -ForegroundColor Yellow
if (-not (Test-Path ".\venv\Scripts\python.exe")) {
    & python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
        Exit 1
    }
    Write-Host "Virtual environment created in .\venv" -ForegroundColor Green
} else {
    Write-Host "Existing virtual environment found in .\venv" -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/4] Installing required dependencies..." -ForegroundColor Yellow
& .\venv\Scripts\python.exe -m pip install --upgrade pip
& .\venv\Scripts\pip.exe install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Dependency installation encountered an issue!" -ForegroundColor Red
    Exit 1
}

Write-Host ""
Write-Host "[4/4] Downloading official MediaPipe Pose Landmarker models..." -ForegroundColor Yellow
& .\venv\Scripts\python.exe download_models.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Model download failed!" -ForegroundColor Red
    Exit 1
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   SETUP COMPLETE! YOU ARE READY TO PLAY!" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
Write-Host "To launch the application, run:" -ForegroundColor Cyan
Write-Host "   .\run.ps1" -ForegroundColor White
Write-Host "or:" -ForegroundColor Cyan
Write-Host "   .\venv\Scripts\python main.py" -ForegroundColor White
Write-Host ""
