@echo off
REM ============================================================
REM  reset-pin.bat - SUPPORT ONLY. Resets owner login to 1234.
REM  Keep on YOUR pen drive, not on the shop PC.
REM  Usage: double-click, type RESET, owner becomes owner / 1234.
REM  Change the PIN immediately after logging in.
REM ============================================================
setlocal
cd /d "%~dp0"
echo SUPPORT ONLY - resets the owner password to 1234.
set /p CONFIRM="Type RESET in capital letters to continue: "
if not "%CONFIRM%"=="RESET" (
    echo Cancelled. Nothing changed.
    pause
    exit /b 1
)
if exist "runtime\python.exe" (
    set PY=runtime\python.exe
) else (
    set PY=venv\Scripts\python.exe
)
if not exist "%PY%" (
    echo ERROR: no Python runtime found - need runtime\ or venv\.
    pause
    exit /b 1
)
"%PY%" manage.py shell -c "from accounts.models import User; u,_=User.objects.update_or_create(username='owner', defaults={'role':'admin','is_active':True,'is_staff':True,'is_superuser':True}); u.set_password('1234'); u.save(); print('owner login reset: owner / 1234')"
if errorlevel 1 (
    echo FAILED - tell the developer what you see above.
    pause
    exit /b 1
)
echo Done. Login as owner / 1234 and CHANGE THE PIN NOW.
pause
