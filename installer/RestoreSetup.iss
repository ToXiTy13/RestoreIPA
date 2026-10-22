; Установщик Restore (Inno Setup 6). Собирается из build.ps1:
;   ISCC.exe /DAppVersion=1.0.0 installer\RestoreSetup.iss
; Ставится без прав администратора (в профиль пользователя); с правами — в Program Files для всех.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Restore"
#define AppExe "RestoreAppStore.exe"

[Setup]
AppId={{BDC18B4B-7B89-4306-9CAB-480F14422EF8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Установщик {#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=RestoreSetup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; при обновлении: библиотеки прошлой версии могут не совпадать с новыми по составу
Type: filesandordirs; Name: "{app}\_internal"

[Files]
; программа папкой (dist\RestoreAppStore\: exe + _internal): в отличие от exe одним файлом,
; ей не нужно при каждом запуске распаковываться во временную папку
Source: "..\dist\RestoreAppStore\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "installed.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; служебная папка программы: сессия ipatool, история и кэш версий, иконки.
; Скачанные .ipa в «Документы\Restore\ipa» не трогаем — это файлы пользователя.
Type: filesandordirs; Name: "{localappdata}\Restore"
