; Installateur Windows FLOPPY (Inno Setup 6). Construit : iscc floppy.iss → dist\FLOPPY-Setup-<version>.exe
#define AppVersion "1.0.1"
[Setup]
AppName=FLOPPY
AppVersion={#AppVersion}
AppPublisher=FLOPPY
DefaultDirName={localappdata}\Programs\FLOPPY
DefaultGroupName=FLOPPY
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=FLOPPY-Setup-{#AppVersion}
SetupIconFile=assets\floppy.ico
UninstallDisplayIcon={app}\FLOPPY.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
[Files]
Source: "dist\FLOPPY\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{group}\FLOPPY"; Filename: "{app}\FLOPPY.exe"
Name: "{autodesktop}\FLOPPY"; Filename: "{app}\FLOPPY.exe"; Tasks: desktopicon
[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau / Create a desktop shortcut"; GroupDescription: "Raccourcis / Shortcuts"
[Run]
Filename: "{app}\FLOPPY.exe"; Description: "Lancer FLOPPY / Launch FLOPPY"; Flags: nowait postinstall skipifsilent
