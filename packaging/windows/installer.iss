; Inno Setup script for the Windows installer. Don't run it directly: use build_windows.ps1,
; which passes AppName, AppVersion, ExeName, SourceUrl, SourceDir and OutputDir.

#ifndef AppVersion
  #error Run packaging/windows/build_windows.ps1 instead of compiling this file directly.
#endif

[Setup]
; AppId must NEVER change, or Windows treats new versions as a different program.
AppId={{A15A7123-39CA-4400-9785-07FE22827F88}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Colter Pan
AppPublisherURL=https://pantechautomation.com
AppSupportURL={#SourceUrl}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Install for the current user without admin rights; users can still choose "all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#ExeName}-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#ExeName}.exe
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Remove libraries from the previous version so upgrades don't mix old and new files.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#ExeName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}.exe"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
