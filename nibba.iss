; nibba Shop - Windows installer (Inno Setup 6).
; Per-user install: no admin rights needed, no UAC prompt.
; Shop data (database, backups, settings, logs) is NEVER removed by
; uninstall - only program files go away, so reinstalling is safe.
; Built by BUILD-INSTALLER.bat: ISCC nibba.iss /DAppVersion=<VERSION>

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "build\\portable\\nibba"
#endif

[Setup]
AppId={{3B2F1A7C-9E4D-4B6A-8C2F-1A5D7E9B2041}
AppName=nibba Shop
AppVersion={#AppVersion}
AppVerName=nibba Shop {#AppVersion}
AppPublisher=nibba
DefaultDirName={localappdata}\nibba
DefaultGroupName=nibba Shop
PrivilegesRequired=lowest
OutputBaseFilename=nibba-Shop-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=nibba Shop
SetupIconFile=assets\nibba.ico
UninstallDisplayIcon={app}\assets\nibba.ico
; Data lives next to the program (single-folder shop install). The
; uninstaller only removes files it installed - database, backups,
; settings and logs are always kept.
DirExistsWarning=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\nibba Shop"; Filename: "{app}\nibba-Shop.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\nibba.ico"
Name: "{group}\Close nibba Shop"; Filename: "{app}\nibba-Close.bat"; WorkingDir: "{app}"; IconFilename: "{app}\assets\nibba.ico"
Name: "{autodesktop}\nibba Shop"; Filename: "{app}\nibba-Shop.bat"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\assets\nibba.ico"

[Tasks]
Name: "desktopicon"; Description: "Desktop icon"; Flags: checkedonce

[Run]
Filename: "{app}\nibba-Shop.bat"; Description: "Open nibba Shop now (first run sets up the shop)"; Flags: postinstall shellexec skipifsilent unchecked
