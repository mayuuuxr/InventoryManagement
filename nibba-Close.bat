@echo off
REM nibba Shop - stops the hidden background server.
setlocal
cd /d "%~dp0"
powershell -NoProfile -WindowStyle Hidden -Command "$c = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue; if ($c) { Stop-Process -Id $c.OwningProcess -Force; Write-Output 'nibba Shop stopped.' } else { Write-Output 'nibba Shop was not running.' }; Start-Sleep -Seconds 3"
exit /b 0
