; sPDF 설치 스크립트 (Inno Setup 6)
; 빌드: build_installer.bat  (먼저 build_exe.bat로 dist\sPDF 생성)
;
; 버전은 bandwagon 방식대로 수동 동기화 — pdfeditor\meta.py의 APP_VERSION과
; 아래 MyAppVersion을 함께 맞출 것(자동 동기화 안 됨).

#define MyAppName "sPDF"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "sPDF"
#define MyAppExeName "sPDF.exe"
#define MyProgId "sPDF.Document"

[Setup]
AppId={{7C2F9A4E-3B71-4E0C-9D2A-5F6B1A8C0E11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=sPDF_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; 관리자면 시스템 전체(HKLM), 아니면 현재 사용자(HKCU)에 설치·등록
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=assets\spdf.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 아이콘 만들기"; GroupDescription: "추가 아이콘:"
; PDF 연결은 '연결 프로그램 후보'로만 등록(기본값을 강제로 뺏지 않음).
; 사용자가 나중에 Windows '기본 앱'에서 sPDF를 직접 고를 수 있다.
Name: "associate"; Description: "PDF 파일 '연결 프로그램' 목록에 sPDF 추가"; GroupDescription: "파일 연결:"
; Windows 8 이상에서는 설치 프로그램이 기본 앱을 직접 바꿀 수 없다.
; 선택 시 설치 완료 후 Windows 기본 앱 설정을 열어 사용자가 확정한다.
Name: "associate\defaultpdf"; Description: "설치 후 sPDF를 기본 PDF 앱으로 선택하기 (Windows 설정 열기)"; GroupDescription: "파일 연결:"; Flags: unchecked

[Files]
Source: "dist\sPDF\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; OCR 워커는 Qt DLL과 격리하기 위해 별도 폴더에 (paths.ocr_command 참고)
Source: "dist\sPDF-ocr\*"; DestDir: "{app}\ocr"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\spdf_doc.ico"; DestDir: "{app}\assets"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; --- ProgId: sPDF로 PDF를 열었을 때의 아이콘/실행 명령 ---
Root: HKA; Subkey: "Software\Classes\{#MyProgId}"; ValueType: string; ValueData: "PDF 문서"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyProgId}\DefaultIcon"; ValueType: string; ValueData: "{app}\assets\spdf_doc.ico"
Root: HKA; Subkey: "Software\Classes\{#MyProgId}\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

; --- .pdf의 '연결 프로그램' 후보 목록에 추가(기본값은 안 건드림) ---
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: none; ValueName: "{#MyProgId}"; Flags: uninsdeletevalue; Tasks: associate

; --- Windows '기본 앱' 목록에 sPDF가 나타나도록 Capabilities 등록 ---
Root: HKA; Subkey: "Software\sPDF\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey; Tasks: associate
Root: HKA; Subkey: "Software\sPDF\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "가벼운 PDF 보기·주석·OCR·편집 도구"; Tasks: associate
Root: HKA; Subkey: "Software\sPDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "{#MyProgId}"; Tasks: associate
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: "Software\sPDF\Capabilities"; Flags: uninsdeletevalue; Tasks: associate

[Run]
Filename: "ms-settings:defaultapps"; Description: "sPDF를 기본 PDF 앱으로 선택하기"; Flags: shellexec nowait skipifsilent runasoriginaluser; Tasks: associate\defaultpdf
Filename: "{app}\{#MyAppExeName}"; Description: "sPDF 실행"; Flags: nowait postinstall skipifsilent
