@echo off
REM ============================================================
REM  BUILD-PORTABLE - builds the shop handover kit (run on YOUR pc)
REM  Output: build\nibba-shop-portable.zip (~100-150 MB)
REM  The zip contains: app code + portable Python (no install needed)
REM  + launchers. NO database, NO .env, NO backups inside.
REM  Shop install = unzip + double-click the icon (5 minutes).
REM ============================================================
setlocal
cd /d "%~dp0"
title nibba portable builder

set PYVER=3.12.10
set PYURL=https://www.python.org/ftp/python/%PYVER%/python-%PYVER%-embed-amd64.zip
set BUILD=%CD%\build\portable
set STAGE=%BUILD%\nibba

echo [1/6] Preparing build folder...
if exist "%BUILD%" rmdir /S /Q "%BUILD%"
mkdir "%BUILD%"
mkdir "%STAGE%\runtime"

echo [2/6] Downloading portable Python %PYVER%...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PYURL%' -OutFile '%BUILD%\py.zip'"
if errorlevel 1 (
    echo FAILED to download. Check internet or edit PYVER in this file.
    pause
    exit /b 1
)
powershell -NoProfile -Command "Expand-Archive -Path '%BUILD%\py.zip' -DestinationPath '%STAGE%\runtime' -Force"
powershell -NoProfile -Command "$p=Get-Content '%STAGE%\runtime\python312._pth'; $p=$p -replace '#import site','import site'; Set-Content '%STAGE%\runtime\python312._pth' $p"
if not exist "%STAGE%\runtime\python.exe" (
    echo FAILED: runtime broken. If %PYVER% was removed from python.org, set a newer PYVER above.
    pause
    exit /b 1
)

echo [3/6] Installing pip + app packages into runtime (few minutes)...
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%BUILD%\get-pip.py'"
"%STAGE%\runtime\python.exe" "%BUILD%\get-pip.py" --no-warn-script-location
"%STAGE%\runtime\Scripts\pip.exe" install -r requirements-pc.txt --no-warn-script-location
if errorlevel 1 (
    echo FAILED installing packages. Check internet and retry.
    pause
    exit /b 1
)

echo [4/6] Copying app code (data and secrets excluded)...
powershell -NoProfile -Command ^
    "$excl = @('venv','runtime','.git','.github','.gitignore','e2e','staticfiles','Backup','Logs','Data','chrome-profile','build','__pycache__','tunnel.log','cloudflared.exe','.env','.env.example','INSTALL.bat','run_all.bat','run.bat','tunnel_env.py','BUILD-PORTABLE.bat','BUILD-INSTALLER.bat','nibba.iss','db.sqlite3','Procfile','seed_catalog.json','UPDATE-MODEL.md'); " ^
    "Get-ChildItem -Force | Where-Object { $excl -notcontains $_.Name } | ForEach-Object { " ^
    "  if ($_.Extension -in '.sqlite3','.pem') { return }; " ^
    "  if ($_.Name -like 'backup_*' -or $_.Name -like 'db_*' -or $_.Name -like '*.docx') { return }; " ^
    "  if ($_.Extension -eq '.md' -and $_.Name -ne 'UPDATE-MODEL.md') { return }; " ^
    "  Copy-Item $_.FullName '%STAGE%' -Recurse -Force }; " ^
    "Get-ChildItem '%STAGE%' -Recurse -Include *.sqlite3,*.pem,.env -File -ErrorAction SilentlyContinue | Remove-Item -Force"
if errorlevel 1 (
    echo FAILED copying code.
    pause
    exit /b 1
)

echo [4b/6] Verifying staged code is current...
venv\Scripts\python.exe -c "import pathlib,sys; s=pathlib.Path(r'%STAGE%'); b=(s/'templates'/'base.html').read_text(); c=(s/'core'/'settings.py').read_text(); ok='vendor/tailwind.js' in b and 'USE_HTTPS_REDIRECT' in c and (s/'static'/'vendor'/'tailwind.js').exists(); print('STAGING-OK' if ok else 'STALE-STAGING'); sys.exit(0 if ok else 1)"
if errorlevel 1 (
    echo STALE STAGING COPY - code did not refresh. Delete build\ and retry.
    pause
    exit /b 1
)
echo [5/6] Verifying the kit boots...
powershell -NoProfile -Command "Set-Content '%STAGE%\.env' ('DJANGO_SECRET_KEY=build-check-only-key' + [Environment]::NewLine + 'DEBUG=True' + [Environment]::NewLine + 'ALLOWED_HOSTS=localhost,127.0.0.1')"
cd /d "%STAGE%"
runtime\python.exe manage.py check
if errorlevel 1 (
    echo KIT CHECK FAILED - fix before shipping.
    cd /d "%~dp0"
    pause
    exit /b 1
)
del "%STAGE%\.env"
cd /d "%~dp0"

echo [6/6] Pruning caches + zipping...
powershell -NoProfile -Command "Get-ChildItem '%STAGE%' -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force; Get-ChildItem '%STAGE%' -Recurse -File -Filter '*.pyc' | Remove-Item -Force"
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmm"') do set KITSTAMP=%%t
set KITZIP=%BUILD%\nibba-shop-portable_%KITSTAMP%.zip
powershell -NoProfile -Command "Compress-Archive -Path '%STAGE%\*' -DestinationPath '%KITZIP%' -Force"
if not exist "%KITZIP%" (
    echo ZIP FAILED - staging is fine at %STAGE%, zip it manually.
    pause
    exit /b 1
)
powershell -NoProfile -Command "Get-ChildItem '%BUILD%\nibba-shop-portable_*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 3 | Remove-Item -Force"
echo.
echo ============================================================
echo  READY: %KITZIP%
echo  Test: unzip to a fresh folder, double-click nibba-Shop icon,
echo  login owner/1234. Then ship that zip on a pen drive.
echo ============================================================
pause
exit /b 0
