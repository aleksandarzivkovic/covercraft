; Inno Setup script for CoverCraft.
; Builds a double-click installer (and matching uninstaller registered in
; Windows' "Apps & Features") around the PyInstaller-built CoverCraft.exe.
;
; Local build:
;   ISCC.exe installer\CoverCraft.iss /DMyAppVersion=1.2.3
;
; (MyAppVersion defaults to 0.0.0-dev if not passed, e.g. for ad-hoc local
; testing.) Expects dist\CoverCraft.exe to already exist - run
; scripts\build.ps1 first.

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

#define MyAppName "CoverCraft"
#define MyAppPublisher "Aleksandar Zivkovic"
#define MyAppURL "https://github.com/aleksandarzivkovic/covercraft"
#define MyAppExeName "CoverCraft.exe"

[Setup]
AppId={{B36F2B8E-6E0B-4E9C-9C2B-6B7B6E9B6C4A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Per-user install, matching CoverCraft's existing convention - no admin
; rights required, and each Windows user gets their own install + session.
DefaultDirName={localappdata}\Programs\CoverCraft
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\assets\icon.ico
OutputDir=..\dist
OutputBaseFilename=CoverCraftSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableWelcomePage=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\CoverCraft.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Tidal session/cache is app state, not user content - clean it up on
; uninstall. Generated PDFs in Documents\CoverCraft are left alone since
; those are the user's actual output, not app state.
Type: filesandordirs; Name: "{userappdata}\CoverCraft"
