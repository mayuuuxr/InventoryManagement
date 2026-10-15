@echo off
REM ============================================================
REM  nibba - ONE-TIME setup for the shop PC (double-click once)
REM  Does everything automatically: checks Python, creates the
REM  app environment, installs it, prepares the database, creates
REM  the owner login, and puts a "nibba Shop" icon on the Desktop.
REM  After this, the shop only ever double-clicks "nibba Shop".
REM ============================================================
setlocal
cd /d "%~dp0"
title nibba Setup

echo ============================================================
echo  nibba - shop setup (one time only)
echo ============================================================

REM --- 1. Python check ---
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo Python is not installed on this PC.
    echo Opening the Python download page - install it, tick
    echo "Add python.exe to PATH", then run INSTALL again.
    start "" "https://www.python.org/downloads/"
    pause
    exit /b 1
)
echo [1/5] Python found.

REM --- 2. App environment ---
if not exist "venv\Scripts\python.exe" (
    echo [2/5] Creating app environment (one minute)...
    python -m venv venv
    if errorlevel 1 (
        echo SETUP FAILED creating venv. Tell support.
        pause
        exit /b 1
    )
) else (
    echo [2/5] App environment already ready.
)

REM --- 3. Install ---
echo [3/5] Installing (2-4 minutes, one time only)...
venv\Scripts\pip install -r requirements-pc.txt
if errorlevel 1 (
    echo SETUP FAILED installing. Check internet, then run INSTALL again.
    pause
    exit /b 1
)

REM --- 4. Database ---
echo [4/5] Preparing database (your stock register)...
venv\Scripts\python.exe manage.py migrate
if errorlevel 1 (
    echo SETUP FAILED preparing database. Tell support.
    pause
    exit /b 1
)
venv\Scripts\python.exe manage.py collectstatic --noinput -v 0

REM --- 5. Owner login (default PIN, change it after first login) ---
venv\Scripts\python.exe manage.py shell -c "from accounts.models import User; u,_=User.objects.update_or_create(username='owner', defaults={'role':'admin','is_active':True,'is_staff':True,'is_superuser':True}); u.set_password('1234'); u.save(); print('owner login ready')"
if errorlevel 1 (
    echo WARNING: owner login was not created. Tell support.
)

REM --- Desktop icon (real Desktop, all Windows versions) ---
powershell -NoProfile -ExecutionPolicy Bypass -File make-shortcut.ps1
if errorlevel 1 (
    echo WARNING: Desktop icon was not created. Open nibba-Shop.bat from this folder daily.
) else (
    echo [5/5] Desktop icon "nibba Shop" created.
)

echo.
echo ============================================================
echo  DONE. From now on just double-click "nibba Shop".
echo  First login:  owner  /  1234   (change the PIN after login)
echo  Support file: README-SHOP.txt
echo ============================================================
pause
exit /b 0
