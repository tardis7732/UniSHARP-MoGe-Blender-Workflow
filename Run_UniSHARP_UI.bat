@echo off
setlocal

rem Double-click this file to set up and start the local UniSHARP browser UI.
cd /d "%~dp0"
set "PYTHON_EXE=.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [UniSHARP] Creating the Python 3.11 virtual environment...
    py -3.11 -m venv .venv
    if errorlevel 1 goto :python_missing
)

"%PYTHON_EXE%" -c "import torch, gradio, gsplat, wandb" >nul 2>&1
if errorlevel 1 goto :install_packages
goto :start_ui

:install_packages
echo [UniSHARP] Installing required packages. This can take several minutes on the first run...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :setup_failed
"%PYTHON_EXE%" -m pip install torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :setup_failed
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto :setup_failed

:start_ui
if not defined BLENDER_EXE if exist "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" set "BLENDER_EXE=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

echo.
echo [UniSHARP] Starting the browser UI at http://127.0.0.1:7860
echo [UniSHARP] Leave this window open while using the program.
"%PYTHON_EXE%" scripts\blender_gui.py
exit /b %errorlevel%

:python_missing
echo.
echo [UniSHARP] Python 3.11 (64-bit) was not found.
echo Install it from https://www.python.org/downloads/, then run this file again.
pause
exit /b 1

:setup_failed
echo.
echo [UniSHARP] Setup failed. Check the messages above, then run this file again.
pause
exit /b 1
