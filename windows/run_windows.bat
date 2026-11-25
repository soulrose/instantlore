@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python not found. Installing Python 3.12 with winget...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo Python installed. Close this window and double-click run_windows.bat again.
  pause
  exit /b
)
if not exist venv\Scripts\python.exe (
  echo First run: setting up, please wait 1-3 minutes...
  py -3 -m venv venv
  venv\Scripts\python -m pip install --upgrade pip
  venv\Scripts\python -m pip install -r requirements.txt
)
start "" venv\Scripts\pythonw.exe instantlore.py
