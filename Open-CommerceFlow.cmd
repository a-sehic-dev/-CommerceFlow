@echo off
setlocal
REM Starts CommerceFlow in the background. It does not open any browser.

for /d %%i in ("%USERPROFILE%\Desktop\*CommerceFlow*") do (
  cd /d "%%i"
  goto :found
)

echo CommerceFlow folder not found on Desktop.
pause
exit /b 1

:found
echo Project folder:
cd
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment was not found: .venv\Scripts\python.exe
  echo Open Cursor in the CommerceFlow folder and run: python -m venv .venv
  pause
  exit /b 1
)

echo Starting CommerceFlow server in the background...
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList 'run.py' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden"
echo.
echo Wait 5 seconds, then paste this in Chrome:
echo http://127.0.0.1:8000
echo.
timeout /t 3 >nul
exit /b 0
