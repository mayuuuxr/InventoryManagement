@echo off
REM nibba Shop - daily opener (the ONLY icon the shop uses).
REM First launch self-initializes (.env, database, owner login).
REM Daily: backup, migrate, start, open. No tunnel, no extra windows.
setlocal
title nibba Shop
cd /d "%~dp0"
if exist "runtime\python.exe" goto havepy
set PY=venv\Scripts\python.exe
set WAITRESS=venv\Scripts\waitress-serve.exe
goto checkpy
:havepy
set PY=runtime\python.exe
set WAITRESS=runtime\Scripts\waitress-serve.exe
:checkpy
if exist "%PY%" goto envstep
echo First run INSTALL.bat once, then open this icon daily.
pause
exit /b 1
:envstep
if exist ".env" goto dbstep
echo First launch: creating shop setup...
call :makeenv
if errorlevel 1 goto envfail
goto dbstep
:envfail
echo SETUP FAILED writing .env. Tell support.
pause
exit /b 1
:dbstep
if exist "db.sqlite3" goto staticstep
echo First launch: preparing stock register...
"%PY%" manage.py migrate
if errorlevel 1 goto dbfail
"%PY%" manage.py shell -c "from accounts.models import User; u,_=User.objects.update_or_create(username='owner', defaults={'role':'admin','is_active':True,'is_staff':True,'is_superuser':True}); u.set_password('1234'); u.save(); print('owner login ready: owner / 1234')"
goto staticstep
:dbfail
echo SETUP FAILED. Tell support what you see above.
pause
exit /b 1
:staticstep
if exist "staticfiles\vendor\tailwind.js" goto backupstep
echo Preparing display files (one time)...
"%PY%" manage.py collectstatic --noinput -v 0
:backupstep
if not exist "Backup" mkdir "Backup"
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmm"') do set STAMP=%%t
if not exist "db.sqlite3" goto servstep
copy /Y "db.sqlite3" "Backup\db_%STAMP%.sqlite3" >nul
powershell -NoProfile -Command "Get-ChildItem 'Backup\db_*.sqlite3' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 30 | Remove-Item -Force"
:servstep
REM Monthly Excel files for direct work (fail-soft: never blocks launch).
"%PY%" manage.py export_monthly_files -v 0
if errorlevel 1 echo WARNING: monthly Excel files not updated - app still opens fine.
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($c) { Stop-Process -Id $c.OwningProcess -Force }"
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
REM Hidden server window: no terminal on screen. Output goes to Logs/nibba.log.
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath '%WAITRESS%' -ArgumentList '--listen=127.0.0.1:8000','core.wsgi:application' -WorkingDirectory '%CD%' -WindowStyle Hidden"
set TRIES=0
:waitloop
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:8000/accounts/login/ | Out-Null; exit 0 } catch { exit 1 }"
if not errorlevel 1 goto openit
powershell -NoProfile -Command "Start-Sleep -Seconds 2"
set /a TRIES=%TRIES%+1
if %TRIES% LSS 30 goto waitloop
echo WARNING: server is slow - opening the browser anyway...
:openit
REM App window: Chrome/Edge --app mode shows no address bar at all, so
REM staff never see localhost URLs. Separate profile keeps shop cookies
REM away from personal browsing. Falls back to the default browser.
set APPURL=http://localhost:8000/accounts/login/
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" goto openchrome
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" goto openchrome86
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" goto openedge
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" goto openedge86
start "" "%APPURL%"
exit /b 0
:openchrome
start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" --app="%APPURL%" --user-data-dir="%CD%\chrome-profile"
exit /b 0
:openchrome86
start "" "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" --app="%APPURL%" --user-data-dir="%CD%\chrome-profile"
exit /b 0
:openedge
start "" "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" --app="%APPURL%" --user-data-dir="%CD%\chrome-profile"
exit /b 0
:openedge86
start "" "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" --app="%APPURL%" --user-data-dir="%CD%\chrome-profile"
exit /b 0
:makeenv
powershell -NoProfile -Command "$k=((48..57)+(65..90)+(97..122) | Get-Random -Count 50 | ForEach-Object {[char]$_}) -join ''; Set-Content '.env' ('DJANGO_SECRET_KEY=' + $k + [Environment]::NewLine + 'DEBUG=False' + [Environment]::NewLine + 'ALLOWED_HOSTS=localhost,127.0.0.1')"
exit /b %errorlevel%
