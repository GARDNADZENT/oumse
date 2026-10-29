; Oumse GSM Tool Pro - Community Edition (No Login)
; Inno Setup 6 script. Build with installer\build_installer.bat on Windows.

#define MyAppName "Oumse GSM Tool Pro - No Login"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Oumse GSM Community"
#define MyAppURL "https://oumsegsm.com/"
#define MyAppId "{{F0C668EF-6B2D-4E40-BEFB-AAFDF5A00BD8}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppComments=Direct-opening, offline community front-end. No login required.
AppCopyright=Copyright (C) 2026 Oumse GSM Community
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
AllowNoIcons=yes
LicenseFile={#SourcePath}..\runtime\lib\LICENSE
InfoAfterFile={#SourcePath}..\README.md
OutputDir={#SourcePath}artifacts
OutputBaseFilename=OumseNoLoginSetup-{#MyAppVersion}
SetupIconFile={#SourcePath}..\app_icon.ico
UninstallDisplayIcon={app}\app_icon.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
MinVersion=10.0
ArchitecturesAllowed=x86 x64
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Oumse GSM Tool Pro no-login installer
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (C) 2026 Oumse GSM Community
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; New no-login application
Source: "{#SourcePath}..\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "{#SourcePath}..\servicecore\*"; DestDir: "{app}\servicecore"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,*.pyo"

; Bundled headless Python runtime for the BROM runner
Source: "{#SourcePath}..\runtime\bin\*"; DestDir: "{app}\runtime\bin"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "Scripts\*,get-pip.py,__pycache__\*,*.pyc,*.pyo,python312._pth"
Source: "{#SourcePath}runtime\python312._pth"; DestDir: "{app}\runtime\bin"; DestName: "python312._pth"; Flags: overwritereadonly ignoreversion

; Vendored mtkclient and custom BROM runners
Source: "{#SourcePath}..\runtime\lib\*"; DestDir: "{app}\runtime\lib"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "logs\*,hwparam.json,python,__pycache__\*,*.pyc,*.pyo,.pytest_cache\*,.ruff_cache\*"

; Windows flashing / ADB tools and CA bundle
Source: "{#SourcePath}..\Bin\*"; DestDir: "{app}\Bin"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourcePath}..\adb_assets\*"; DestDir: "{app}\adb_assets"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourcePath}..\certifi\*"; DestDir: "{app}\certifi"; Flags: recursesubdirs createallsubdirs ignoreversion

; Launcher, icon, docs, and metadata
Source: "{#SourcePath}launcher\*"; DestDir: "{app}\launcher"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourcePath}..\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\START_NO_LOGIN.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\run_gui.sh"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\PROJECT_ANALYSIS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\requirements-dev.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}README.md"; DestDir: "{app}"; DestName: "INSTALLER.md"; Flags: ignoreversion
Source: "{#SourcePath}version.txt"; DestDir: "{app}"; DestName: "VERSION.txt"; Flags: ignoreversion
Source: "{#SourcePath}..\runtime\lib\LICENSE"; DestDir: "{app}"; DestName: "LICENSE-mtkclient.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Oumse GSM Tool Pro (No Login)"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher\Launch-OumseNoLogin.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0
Name: "{group}\README"; Filename: "{app}\README.md"
Name: "{group}\Uninstall Oumse GSM Tool Pro"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Oumse GSM Tool Pro (No Login)"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher\Launch-OumseNoLogin.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0; Tasks: desktopicon

[Registry]
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Run]
Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher\Launch-OumseNoLogin.vbs"""; WorkingDir: "{app}"; Description: "Launch Oumse GSM Tool Pro (No Login)"; Flags: nowait postinstall skipifsilent unchecked

[UninstallDelete]
Type: filesandordirs; Name: "{app}\app\__pycache__"
Type: filesandordirs; Name: "{app}\runtime\lib\logs"
Type: files; Name: "{app}\*.log"
Type: files; Name: "{app}\.remember.dat"
Type: files; Name: "{app}\hwparam.json"

[Code]
function IsPythonWithTkAvailable(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('py', '-3 -c "import tkinter"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
  if not Result then
    if Exec('python', '-c "import tkinter"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Result := (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsPythonWithTkAvailable() then
    MsgBox('Python 3.10 or newer with Tkinter was not detected on this PC.' + #13#10 +
           'The installer will continue, but the no-login GUI needs it to start.' + #13#10 +
           'Install Python from python.org with the tcl/tk option enabled.',
           mbInformation, MB_OK);
end;
