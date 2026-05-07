@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows\start-vercel-site.ps1"
if errorlevel 1 (
  echo.
  echo Public Vercel launcher failed. Check the messages above.
  pause
)
endlocal
