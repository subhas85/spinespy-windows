#define AppName "SpineSpy"
#define AppVersion "0.1.0"
#define AppExe "SpineSpy.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=subhas85
DefaultDirName={localappdata}\Programs\SpineSpy
DefaultGroupName=SpineSpy
PrivilegesRequired=lowest
OutputBaseFilename=SpineSpy-Setup
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes

[Files]
Source: "..\dist\SpineSpy\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\SpineSpy"; Filename: "{app}\{#AppExe}"
Name: "{userstartup}\SpineSpy"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch SpineSpy"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
