#define MyAppName "Драконья Сага"
#define MyAppVersion "4.0.0"
#ifndef MySourceDir
  #define MySourceDir "..\\dist\\DragonSaga"
#endif
[Setup]
AppId={{5DBB9207-5D3B-4DB7-B4C1-D53000000000}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Dragon Saga
DefaultGroupName={#MyAppName}
OutputDir=..\release
OutputBaseFilename=Dragon-Saga-4.0.0-Windows-x64-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=dragon-saga.ico
UninstallDisplayName={#MyAppName}
[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\DragonSaga.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\DragonSaga.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"
[Run]
Filename: "{app}\DragonSaga.exe"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
