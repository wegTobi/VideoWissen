@echo off
cd /d "%~dp0"
if exist "VideoWissen.exe" (
  start "" "%~dp0VideoWissen.exe"
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  echo Bitte zuerst install.ps1 ausfuehren. Siehe README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause

