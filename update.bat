@echo off
REM ============================================================
REM  nibba updater - applies a GitHub Release WITHOUT touching data
REM  Protected (never overwritten): *.sqlite3, .env, Backup/,
REM  venv/, runtime/, tunnel.log, cloudflared.exe, .git/, staticfiles/
REM  Safety: if the pre-update backup FAILS, the update ABORTS
REM  before a single code file is touched.
REM
REM  Usage:  update.bat v1.1.0
REM  (Find the version on the Help page under App updates.)
REM  Close the server windows first (port 8000 must be free).
REM ============================================================
setlocal
cd /d "%~dp0"

REM --- Python: portable runtime first, dev venv fallback ---
if exist "runtime\python.exe" (
    set PY=runtime\python.exe
    set PIP=runtime\Scripts\pip.exe
) else (
    set PY=venv\Scripts\python.exe
    set PIP=venv\Scripts\pip.exe
)
if not exist "%PY%" (
    echo ERROR: no Python runtime found - need runtime\ or venv\.
    pause
    exit /b 1
)

REM --- 0. Server must be stopped (Windows locks running files) ---
powershell -NoProfile -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($c) { Write-Output 'BUSY' }" > "%TEMP%\nibba_port.txt"
findstr /C:"BUSY" "%TEMP%\nibba_port.txt" >nul
if not errorlevel 1 (
    echo ERROR: server still running on port 8000.
    echo Close the "nibba Shop" / "nibba Server" windows, then retry.
    pause
    exit /b 1
)

REM --- 1. BACKUP FIRST: abort unless a fresh backup is verified ---
if not exist "Backup" mkdir "Backup"
for /f %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set STAMP=%%t
set BACKUP_FILE=Backup\pre-update_%STAMP%.sqlite3
if not exist "db.sqlite3" (
    echo ERROR: db.sqlite3 missing - refusing to update without data to back up.
    pause
    exit /b 1
)
copy /Y "db.sqlite3" "%BACKUP_FILE%" >nul
if errorlevel 1 (
    echo ERROR: backup copy failed - update ABORTED, nothing was changed.
    pause
    exit /b 1
)
for %%f in ("%BACKUP_FILE%") do set BACKUP_SIZE=%%~zf
for %%f in ("db.sqlite3") do set DB_SIZE=%%~zf
if not "%BACKUP_SIZE%"=="%DB_SIZE%" (
    echo ERROR: backup size mismatch - db=%DB_SIZE%, backup=%BACKUP_SIZE% - ABORTED, nothing changed.
    del "%BACKUP_FILE%"
    pause
    exit /b 1
)
echo Backup verified: %BACKUP_FILE% (%BACKUP_SIZE% bytes)
powershell -NoProfile -Command "Get-ChildItem 'Backup\pre-update_*.sqlite3' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 | Remove-Item -Force"

REM --- 2. Resolve the release zip URL ---
set TAG=%1
if "%TAG%"=="" (
    echo Usage: update.bat v1.1.0
    echo  Find the version on the Help page under App updates.
    pause
    exit /b 1
)
REM UPDATE_REPO: process env first, then .env, then this repo (baked).
if "%UPDATE_REPO%"=="" if exist ".env" for /f "eol=# tokens=1,* delims==" %%a in (.env) do if /i "%%a"=="UPDATE_REPO" if not defined UPDATE_REPO set "UPDATE_REPO=%%b"
if "%UPDATE_REPO%"=="" set UPDATE_REPO=mayuuuxr/InventoryManagement
set ZIP_URL=https://github.com/%UPDATE_REPO%/releases/download/%TAG%/nibba-%TAG%.zip
echo Downloading %ZIP_URL% ...
powershell -NoProfile -Command "Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\nibba_update.zip'"
if errorlevel 1 (
    echo ERROR: download failed - your data and code are untouched, backup at %BACKUP_FILE%.
    pause
    exit /b 1
)

REM --- 3. Extract + copy code only (protected names excluded) ---
if exist "%TEMP%\nibba_update" rmdir /S /Q "%TEMP%\nibba_update"
mkdir "%TEMP%\nibba_update"
powershell -NoProfile -Command "Expand-Archive -Path '%TEMP%\nibba_update.zip' -DestinationPath '%TEMP%\nibba_update' -Force"
if errorlevel 1 (
    echo ERROR: zip extract failed - nothing changed, backup at %BACKUP_FILE%.
    pause
    exit /b 1
)
echo Copying code files (data files skipped)...
powershell -NoProfile -Command ^
    "$prot = @('.env','Backup','Logs','Data','chrome-profile','venv','runtime','.git','staticfiles','__pycache__','tunnel.log','cloudflared.exe'); " ^
    "Get-ChildItem '%TEMP%\nibba_update' -Recurse -File | ForEach-Object { " ^
    "  $rel = $_.FullName.Substring('%TEMP%\nibba_update'.Length + 1); " ^
    "  $parts = $rel -split '[\\/]'; " ^
    "  if (($parts | Where-Object { $prot -contains $_ }).Count -gt 0) { return }; " ^
    "  if ($rel -like '*.sqlite3' -or $rel -like '*.pem') { return }; " ^
    "  $dest = Join-Path '.' $rel; " ^
    "  New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null; " ^
    "  Copy-Item $_.FullName $dest -Force }"
if errorlevel 1 (
    echo ERROR: file copy failed mid-way - restore %BACKUP_FILE% over db.sqlite3 if needed, then tell support.
    pause
    exit /b 1
)

REM --- 4. Sync packages (new release may need new libraries) + migrate ---
"%PIP%" install -r requirements-pc.txt
if errorlevel 1 (
    echo WARNING: package sync had errors - continuing with migrate anyway.
)
"%PY%" manage.py migrate
if errorlevel 1 (
    echo ERROR: migrate failed - code updated but DB untouched except backup.
    echo Your data is safe at %BACKUP_FILE%. Tell support before restarting.
    pause
    exit /b 1
)
"%PY%" manage.py collectstatic --noinput -v 0
"%PY%" manage.py check
echo.
echo ============================================================
echo  Updated. Data continued from %BACKUP_FILE% source (untouched).
echo  Start with the "nibba Shop" icon. Version now:
"%PY%" -c "print(open('VERSION').read().strip())"
echo ============================================================
pause
exit /b 0
