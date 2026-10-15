@echo off
REM ============================================================
REM  BUILD-INSTALLER - builds nibba-Shop-Setup-vX.exe (run on YOUR pc)
REM  Needs: build\portable\nibba staging (run BUILD-PORTABLE first)
REM  and Inno Setup 6 (winget install JRSoftware.InnoSetup -e).
REM  Output: build\installer\nibba-Shop-Setup-v<version>.exe
REM  Per-user install: no admin rights, data survives uninstall.
REM ============================================================
setlocal
cd /d "%~dp0"

for /f "tokens=* delims= " %%v in (VERSION) do set VER=%%v
if "%VER%"=="" (
    echo ERROR: VERSION file empty.
    pause
    exit /b 1
)

if not exist "build\portable\nibba\manage.py" (
    echo ERROR: staging missing. Run BUILD-PORTABLE.bat first.
    pause
    exit /b 1
)

set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" (
    echo ERROR: ISCC.exe not found. Install once:
    echo   winget install --id JRSoftware.InnoSetup -e --silent
    pause
    exit /b 1
)

if not exist "build\installer" mkdir "build\installer"
echo Building installer for v%VER%...
"%ISCC%" nibba.iss /DAppVersion=%VER% /DSourceDir="build\portable\nibba" /O"build\installer"
if errorlevel 1 (
    echo BUILD FAILED - see messages above.
    pause
    exit /b 1
)
echo.
echo ============================================================
echo  READY: build\installer\nibba-Shop-Setup-v%VER%.exe
echo  Test: install with /DIR to a test folder, open from Start menu.
echo ============================================================
pause
exit /b 0
