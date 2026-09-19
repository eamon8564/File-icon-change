@echo off
setlocal
cd /d "%~dp0"
set "SKIN_PYTHON=E:\Anaconda\envs\comp5310\python.exe"
if not exist "%SKIN_PYTHON%" (
  echo Python not found. Edit SKIN_PYTHON in Start.cmd.
  pause
  exit /b 1
)
"%SKIN_PYTHON%" app.py
if errorlevel 1 pause
