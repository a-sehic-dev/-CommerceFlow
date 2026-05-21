@echo off
REM Opens CMD already inside CommerceFlow (for git push, status, etc.)
for /d %%i in ("%USERPROFILE%\Desktop\*CommerceFlow*") do (
  cd /d "%%i"
  goto :found
)
echo CommerceFlow folder not found on Desktop.
pause
exit /b 1
:found
echo.
echo Git project folder:
cd
echo.
echo Examples:
echo   git status
echo   git push -u origin main
echo.
cmd /k
