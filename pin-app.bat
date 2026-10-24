@echo off
REM =================================================================
REM nibba pin-app  —  pins "nibba Shop" to the Windows Start menu and
REM the Desktop so the Windows SEARCH BAR finds the app when someone
REM types "nibba". Windows never indexes AppData\Local, so the bare
REM nibba-Shop.bat inside the install folder is invisible to search —
REM this turns the app into a real, searchable Windows app.
REM
REM Idempotent: safe to run any time (re-creates the two shortcuts).
REM Offline only: the .ico is BUILT from this app's own PWA icon with
REM the .NET classes that ship with Windows (no downloads, no new
REM dependencies — repo rule honored).
REM Called automatically (quiet) by nibba-Shop.bat on first open.
setlocal
title nibba pin-app
cd /d "%~dp0"
set QUIET=0
if /i "%~1"=="quiet" set "QUIET=1"

set "LNK_START=%APPDATA%\Microsoft\Windows\Start Menu\Programs\nibba Shop.lnk"

REM ---- 1. Build nibba.ico from the PWA icon (cached; skip if built) ----
if exist "nibba.ico" goto shortcuts
if not exist "core\pwa_files\icon-512.png" goto noicon
powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Drawing; $src=[System.Drawing.Image]::FromFile('%CD%\core\pwa_files\icon-512.png'); $sizes=@(16,32,48,64,128,192,256); $pngs=@{}; foreach($s in $sizes){ $b=New-Object System.Drawing.Bitmap($s,$s); $g=[System.Drawing.Graphics]::FromImage($b); $g.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic; $g.DrawImage($src,0,0,$s,$s); $g.Dispose(); $m=New-Object System.IO.MemoryStream; $b.Save($m,[System.Drawing.Imaging.ImageFormat]::Png); $pngs[$s]=$m.ToArray(); $b.Dispose() }; $src.Dispose(); $cnt=$pngs.Count; $out=New-Object System.IO.MemoryStream; $w=New-Object System.IO.BinaryWriter($out); $w.Write([uint16]0); $w.Write([uint16]1); $w.Write([uint16]$cnt); foreach($s in $sizes){ $d=$pngs[$s]; $wh=if($s -ge 256){[byte]0}else{[byte]$s}; $w.Write($wh); $w.Write($wh); $w.Write([byte]0); $w.Write([byte]0); $w.Write([uint16]1); $w.Write([uint16]32); $w.Write([uint32]$d.Length); $w.Write([uint32](6+16*$cnt)) }; foreach($s in $sizes){ $w.Write($pngs[$s]) }; $w.Flush(); [System.IO.File]::WriteAllBytes('%CD%\nibba.ico',$out.ToArray()); $w.Close()"
if errorlevel 1 goto noicon
goto shortcuts
:noicon
echo WARNING: could not build nibba.ico - shortcuts get the default icon.

:shortcuts
REM ---- 2. Start menu shortcut (this is what the search bar reads) ----
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $sc=$ws.CreateShortcut('%APPDATA%\Microsoft\Windows\Start Menu\Programs\nibba Shop.lnk'); $sc.TargetPath='%~dp0nibba-Shop.bat'; $sc.WorkingDirectory='%~dp0'; $sc.IconLocation='%CD%\nibba.ico,0'; $sc.Description='Open the nibba shop app (starts the local server, opens the app window)'; $sc.Save()"
if errorlevel 1 goto lnkfail
if not exist "%LNK_START%" goto lnkfail

REM ---- 3. Desktop shortcut ----
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $lnk=Join-Path ([Environment]::GetFolderPath('Desktop')) 'nibba Shop.lnk'; $sc=$ws.CreateShortcut($lnk); $sc.TargetPath='%~dp0nibba-Shop.bat'; $sc.WorkingDirectory='%~dp0'; $sc.IconLocation='%CD%\nibba.ico,0'; $sc.Description='Open the nibba shop app'; $sc.Save()"
if errorlevel 1 goto lnkfail

if %QUIET%==1 exit /b 0
echo Done: "nibba Shop" is now pinned clean —
echo   - Windows Start menu  -> type "nibba" to find it
echo   - Desktop             -> "nibba Shop" icon
pause
exit /b 0

:lnkfail
echo WARNING: shortcut creation failed on this PC.
if %QUIET%==1 exit /b 0
echo Pin by hand: cmd here, run this again, or pin nibba-Shop.bat manually.
pause
exit /b 1
