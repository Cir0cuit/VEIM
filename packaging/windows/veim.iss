; Inno Setup script for the VEIM installer.
;
;   iscc /DAppVersion=2.1.0 packaging\windows\veim.iss
;
; Expects PyInstaller's one-directory bundle in dist\VEIM.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName "VEIM"
#define AppPublisher "Cir0cuit"
#define AppURL "https://github.com/Cir0cuit/VEIM"
#define AppExe "VEIM.exe"

[Setup]
AppId={{7B3F2C41-9E6A-4A2D-9C58-5F1A0D4B7E11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist\installer
OutputBaseFilename=VEIM-{#AppVersion}-windows-setup
SetupIconFile=..\..\src\assets\branding\veim.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; No administrator rights by default, so no UAC prompt for a per-user install.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\..\dist\VEIM\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The logo cache and the update-check record, both regenerated on demand.
Type: filesandordirs; Name: "{localappdata}\VEIM"
