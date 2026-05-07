@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\start-site.ps1" -StopOnly
if errorlevel 1 (
  echo.
  echo Stop command failed. Check the messages above.
  pause
)
endlocal
