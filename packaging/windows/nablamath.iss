#define ProductName "NablaMath"
#ifndef ProductVersion
  #define ProductVersion "0.1.0a1"
#endif
[Setup]
AppId={{D275F794-8209-440C-A8CE-A59877D6EA59}
AppName={#ProductName}
AppVersion={#ProductVersion}
DefaultDirName={localappdata}\Programs\NablaMath
DefaultGroupName=NablaMath
OutputDir=..\..\release
OutputBaseFilename=NablaMath-Setup-Windows
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\NablaMath.exe
[Files]
Source: "..\..\dist\NablaMath\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\NablaMath"; Filename: "{app}\NablaMath.exe"
Name: "{autodesktop}\NablaMath"; Filename: "{app}\NablaMath.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Criar ícone na área de trabalho"; Flags: unchecked
[Run]
Filename: "{app}\NablaMath.exe"; Description: "Abrir laboratório local"; Flags: nowait postinstall skipifsilent
