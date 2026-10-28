@echo off
setlocal

rem Use one setup implementation so both launchers enforce the same venv rules.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_env.ps1"
set "setup_exit_code=%errorlevel%"

pause
exit /b %setup_exit_code%
