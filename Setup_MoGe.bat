@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run Run_UniSHARP_UI.bat once to install the base environment first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\setup_moge.py
if errorlevel 1 (
  echo MoGe setup failed. Check the messages above.
  pause
  exit /b 1
)
pause
