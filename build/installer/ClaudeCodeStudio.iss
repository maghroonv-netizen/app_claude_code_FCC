; ---------------------------------------------------------------------------
; Claude Code Studio — Inno Setup installer
;
; Compile with:
;   iscc /DAPPVERSION=1.0.0 build\installer\ClaudeCodeStudio.iss
; (tools/build_windows.py does this for you on Windows.)
;
; Defines:
;   AppVersion   version shown everywhere (default 1.0.0)
;   SourceDir    the folder produced by PyInstaller (onedir layout)
;   OutputDir    where the setup .exe is written
; ---------------------------------------------------------------------------

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\build\output\ClaudeCodeStudio"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\build\output"
#endif

#define MyAppName "Claude Code Studio"
#define MyAppShort "ClaudeCodeStudio"
#define MyAppPublisher "FCC"
#define MyAppExeName "ClaudeCodeStudio.exe"
#define MyAppUrl "https://github.com/maghroonv-netizen/app_claude_code_FCC"

[Setup]
AppId={{7C1E4A2B-9F36-4D8B-B0A7-2E9C51D6A8F4}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} {#AppVersion}
AppPublisher={#MyAppPublisher}
AppSupportURL={#MyAppUrl}
AppUpdatesURL={#MyAppUrl}
DefaultDirName={autopf}\{#MyAppShort}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=ClaudeCodeStudio-Setup-{#AppVersion}-x64
SetupIconFile=..\..\assets\installer.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSmallImageFile=..\..\assets\installer.png
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=6.1.7601
CloseApplications=yes
RestartApplications=no
CreateUninstallRegKey=yes
UninstallDisplayName={#MyAppName}
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
ShowLanguageDialog=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startmenu"; Description: "Create Start Menu shortcuts"; GroupDescription: "Additional shortcuts:"
Name: "installcli"; Description: "Install the Claude Code CLI now (needs Node.js 18+)"; GroupDescription: "Claude Code backend:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} (safe console mode)"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--console-log"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; Flags: nowait postinstall skipifsilent shellexec

[Registry]
Root: HKCU; Subkey: "Software\Classes\claudecode-studio"; ValueType: string; ValueName: ""; ValueData: "URL:Claude Code Studio"; Flags: uninsdeletekey dontcreatekey

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"

[Code]
function FindClaude(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('cmd.exe', '/c where claude', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
  if not Result then
    if Exec('cmd.exe', '/c claude --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      Result := (ResultCode = 0);
end;

function FindNode(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c node --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode)
             and (ResultCode = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep <> ssPostInstall then
    Exit;

  if IsTaskSelected('installcli') then
  begin
    if FindNode() then
    begin
      WizardForm.StatusLabel.Caption := 'Installing Claude Code CLI with npm (this can take a minute)…';
      if Exec('cmd.exe', '/c npm install -g @anthropic-ai/claude-code', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
      begin
        if ResultCode <> 0 then
          MsgBox('npm reported an error (code ' + IntToStr(ResultCode) + ').' + #13#10 +
                 'You can install Claude Code later with:' + #13#10 +
                 'npm install -g @anthropic-ai/claude-code', mbInformation, MB_OK);
      end;
    end
    else
      MsgBox('Node.js was not found, so Claude Code could not be installed automatically.' + #13#10 +
             'Install Node.js 18+, then run: npm install -g @anthropic-ai/claude-code',
             mbInformation, MB_OK);
  end;

  if not FindClaude() then
    MsgBox('{#MyAppName} is installed, but the Claude Code CLI was not found on PATH.' + #13#10#13#10 +
           'The app still opens (it shows setup steps), but to chat with Claude you need:' + #13#10 +
           '    npm install -g @anthropic-ai/claude-code' + #13#10 +
           'then run "claude" once in a terminal and sign in with /login.',
           mbInformation, MB_OK);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    { nothing to clean outside {app}; user data lives in %APPDATA%\ClaudeCodeStudio }
  end;
end;
