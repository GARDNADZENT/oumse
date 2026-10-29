; BestMDMTool - Authorized Device Service
; Inno Setup 6 script. Build with installer-bestmdmtool\build_installer.bat on Windows.

#define MyAppName "BestMDMTool"
#define MyAppVersion "0.3.0"
#define MyAppPublisher "BestMDMTool"
#define MyAppURL "https://example.com/"
#define MyAppId "{{D3968000-4976-4AF9-91CA-0D5EF2E71E60}"

; Standalone BestMDMTool.exe (built by build_exe.ps1) lets end users run the
; app without installing Python. When it is missing we fall back to the
; source-mode launcher that needs Python 3.10+ with Tkinter.
#define FrozenBundle AddBackslash(SourcePath) + "frozen\BestMDMTool\BestMDMTool.exe"
#if FileExists(FrozenBundle)
  #define HasFrozenBundle
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppComments=Authorized device service tool. No login required.
AppCopyright=Copyright (C) 2026 BestMDMTool
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
AllowNoIcons=yes
LicenseFile={#SourcePath}..\runtime\lib\LICENSE
InfoAfterFile={#SourcePath}..\bestmdmtool\README.md
OutputDir={#SourcePath}artifacts
OutputBaseFilename=BestMDMToolSetup-{#MyAppVersion}
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
VersionInfoVersion=0.3.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=BestMDMTool installer
VersionInfoTextVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (C) 2026 BestMDMTool
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; New no-login application
Source: "{#SourcePath}..\bestmdmtool\*"; DestDir: "{app}\bestmdmtool"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,*.pyo"
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
; Standalone GUI (needs no Python) when build_exe.ps1 has been run
Source: "{#SourcePath}frozen\BestMDMTool\*"; DestDir: "{app}\BestMDMTool"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist; Excludes: "__pycache__\*,*.pyc,*.pyo"

Source: "{#SourcePath}launcher\*"; DestDir: "{app}\launcher"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#SourcePath}..\app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\START_BEST_MDM_TOOL.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\run_bestmdmtool.sh"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\bestmdmtool\README.md"; DestDir: "{app}"; DestName: "BEST_MDM_TOOL.md"; Flags: ignoreversion
Source: "{#SourcePath}..\SECURITY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\PROJECT_ANALYSIS.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\requirements-dev.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}..\pyproject.toml"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourcePath}README.md"; DestDir: "{app}"; DestName: "INSTALLER.md"; Flags: ignoreversion
Source: "{#SourcePath}version.txt"; DestDir: "{app}"; DestName: "VERSION.txt"; Flags: ignoreversion
Source: "{#SourcePath}..\runtime\lib\LICENSE"; DestDir: "{app}"; DestName: "LICENSE-mtkclient.txt"; Flags: ignoreversion

[Icons]
; Primary shortcut: standalone executable (no Python needed)
Name: "{group}\BestMDMTool"; Filename: "{app}\BestMDMTool\BestMDMTool.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0; Check: FileExists(ExpandConstant('{app}\BestMDMTool\BestMDMTool.exe'))
Name: "{autodesktop}\BestMDMTool"; Filename: "{app}\BestMDMTool\BestMDMTool.exe"; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0; Tasks: desktopicon; Check: FileExists(ExpandConstant('{app}\BestMDMTool\BestMDMTool.exe'))

; Fallback shortcut: runs the Python sources, needs Python 3.10+ with Tkinter
Name: "{group}\BestMDMTool (Python launcher)"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher\Launch-BestMDMTool.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0; Check: not FileExists(ExpandConstant('{app}\BestMDMTool\BestMDMTool.exe'))
Name: "{autodesktop}\BestMDMTool (Python launcher)"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher\Launch-BestMDMTool.vbs"""; WorkingDir: "{app}"; IconFilename: "{app}\app_icon.ico"; IconIndex: 0; Tasks: desktopicon; Check: not FileExists(ExpandConstant('{app}\BestMDMTool\BestMDMTool.exe'))

Name: "{group}\README"; Filename: "{app}\README.md"
Name: "{group}\Uninstall BestMDMTool"; Filename: "{uninstallexe}"

[Registry]
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Run]
Filename: "{app}\BestMDMTool\BestMDMTool.exe"; WorkingDir: "{app}"; Description: "Launch BestMDMTool"; Flags: nowait postinstall skipifsilent unchecked; Check: FileExists(ExpandConstant('{app}\BestMDMTool\BestMDMTool.exe'))
Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher\Launch-BestMDMTool.vbs"""; WorkingDir: "{app}"; Description: "Launch BestMDMTool"; Flags: nowait postinstall skipifsilent unchecked; Check: not FileExists(ExpandConstant('{app}\BestMDMTool\BestMDMTool.exe'))

[UninstallDelete]
Type: filesandordirs; Name: "{app}\bestmdmtool\__pycache__"
Type: filesandordirs; Name: "{app}\servicecore\__pycache__"
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
#ifndef HasFrozenBundle
  // This build ships only the Python sources, so Python with Tkinter is required.
  if not IsPythonWithTkAvailable() then
    MsgBox('Python 3.10 or newer with Tkinter was not detected on this PC.' + #13#10 +
           'The installer will continue, but BestMDMTool needs it to start.' + #13#10 +
           'Install Python from python.org with the tcl/tk option enabled.',
           mbInformation, MB_OK);
#endif
end;
