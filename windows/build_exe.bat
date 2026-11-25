@echo off
rem Optional: build a single InstantLore.exe (run run_windows.bat once first)
cd /d "%~dp0"
venv\Scripts\python -m pip install pyinstaller
venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name InstantLore --collect-all rapidocr instantlore.py
echo Done: dist\InstantLore.exe
pause
