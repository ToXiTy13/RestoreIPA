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
OutputDir=..\dist
OutputBaseFilename=RestoreSetup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
; оформление в цветах программы: светлый стиль Windows 11 без разделительных линий, белый фон,
; картинки мастера рисует installer\make_art.py (Inno сам берёт подходящую под масштаб экрана)
WizardStyle=modern light windows11 hidebevels
WizardBackColor=white
WizardImageFile=wizard\image-100.png,wizard\image-125.png,wizard\image-150.png,wizard\image-175.png,wizard\image-200.png
WizardSmallImageFile=wizard\small-100.png,wizard\small-125.png,wizard\small-150.png,wizard\small-175.png,wizard\small-200.png
WizardImageBackColor=#0d9488
WizardSmallImageBackColor=white
; шагов минимум: приветствие → папка (только при первой установке) → ярлык → установка → готово.
; Лицензия GPL-3.0 не требует принятия для использования: файл LICENSE.txt кладётся в папку программы
DisableWelcomePage=no
DisableReadyPage=yes
; окно выбора языка — только если язык Windows не русский и не английский
ShowLanguageDialog=auto
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Messages]
russian.WelcomeLabel1=Restore {#AppVersion}
russian.WelcomeLabel2=Вернёт на iPhone приложения, которые пропали из российского App Store: банки, госуслуги, сервисы.%n%nУстановка займёт меньше минуты. Права администратора не нужны.%n%nПрограмма бесплатная, с открытым кодом (лицензия GPL-3.0).
russian.SelectDirDesc=Куда поставить Restore?
russian.SelectDirLabel3=Restore будет установлена в эту папку.
russian.WizardSelectTasks=Ярлык
russian.SelectTasksDesc=Нужен ли значок на рабочем столе?
russian.SelectTasksLabel2=Значок в меню «Пуск» появится в любом случае.
russian.InstallingLabel=Подождите немного — Restore устанавливается.
russian.FinishedHeadingLabel=Restore установлена
russian.FinishedLabel=Программа в меню «Пуск». Для начала войдите в Apple ID и подключите iPhone кабелем.
russian.FinishedLabelNoIcons=Для начала войдите в Apple ID и подключите iPhone кабелем.
russian.ClickFinish=

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

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

[Code]
// страница «Ярлык» — последняя перед установкой (страница «Всё готово» отключена): кнопка сразу «Установить»
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpSelectTasks then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
end;
