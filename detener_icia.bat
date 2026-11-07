@echo off
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" -m app.stop
) else if exist "%~dp0ICIA.exe" (
  start "" "%~dp0ICIA.exe" --detener
)
exit /b 0
