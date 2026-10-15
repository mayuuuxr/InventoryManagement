# Creates the Desktop icons. Called by INSTALL.bat.
# Main icon runs minimized (brief flash only); the server itself is hidden.
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$d = [Environment]::GetFolderPath('Desktop')
$icon = Join-Path $appDir "assets\nibba.ico"
if (!(Test-Path $icon)) { $icon = "$env:SystemRoot\System32\shell32.dll,21" }
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$d\nibba Shop.lnk")
$s.TargetPath = 'cmd.exe'
$s.Arguments = '/c ""' + $appDir + '\nibba-Shop.bat""'
$s.WorkingDirectory = $appDir
$s.IconLocation = $icon
$s.WindowStyle = 7
$s.Save()
$c = (New-Object -ComObject WScript.Shell).CreateShortcut("$d\Close nibba Shop.lnk")
$c.TargetPath = 'cmd.exe'
$c.Arguments = '/c ""' + $appDir + '\nibba-Close.bat""'
$c.WorkingDirectory = $appDir
$c.IconLocation = $icon
$c.WindowStyle = 7
$c.Save()
Write-Output "SHORTCUT-OK"
