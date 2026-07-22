# sPDF

가벼운 데스크톱 PDF 편집기 (PyQt5 + PyMuPDF). 설계 전반은 [PLAN.md](PLAN.md),
오픈소스 고지는 [LICENSES.md](LICENSES.md) 참고.

## 설치

```bash
pip install PyQt5 PyMuPDF
pip install rapidocr onnxruntime   # OCR
```

## 실행

```bash
python run.py            # 콘솔 표시 — 개발/디버그용
python run.py 파일.pdf   # PDF를 열면서 시작
```

`run.pyw`는 콘솔 없이 더블클릭/탐색기 연동용.

## 설치 파일 빌드 (Windows)

```bat
build_exe.bat        REM PyInstaller -> dist\sPDF\sPDF.exe (아이콘 자동 생성)
build_installer.bat  REM Inno Setup  -> Output\sPDF_Setup_X.X.X.exe
```

- 아이콘은 `make_icons.py`가 Pillow로 생성한다(`assets\spdf.ico` 앱,
  `assets\spdf_doc.ico` 연결된 PDF 문서).
- OCR 모델(det+cls+한국어 rec, 약 21MB)은 설치본에 번들되어 **오프라인**
  동작한다(`spdf.spec`의 `_KEEP_MODELS` 화이트리스트). 안 쓰는 중국어 rec은
  제외.
- 버전은 `pdfeditor\meta.py`의 `APP_VERSION`과 `installer.iss`의
  `MyAppVersion`을 **함께** 맞출 것(자동 동기화 안 됨).

설치 시 "PDF 파일 '연결 프로그램' 목록에 sPDF 추가"를 선택하면 탐색기
우클릭 → "연결 프로그램"에 나타나고, Windows '기본 앱'에서 sPDF를 기본
PDF 앱으로 고를 수 있다(보안상 설치 프로그램이 기본값을 강제로 바꾸지는
않음). 하위 옵션인 "설치 후 sPDF를 기본 PDF 앱으로 선택하기"를 체크하면
설치 완료 후 Windows 기본 앱 설정이 열린다. 도움말 → **PDF 기본 프로그램 /
브라우저 설정**에서는 현재 연결을 확인하고, Edge·Chrome·Firefox의 PDF 링크를
Windows 기본 PDF 앱(sPDF)으로 넘기는 사용자별 정책을 켜고 끌 수 있다.

## 탐색기에서 열기 (설치 없이, 개발용)

```bash
python register_filetype.py              # 등록
python register_filetype.py --unregister # 해제
```

## 별도 도구: Paper Organizer

논문 자동 정리는 sPDF 본체와 분리된 `paper_organizer.py`에서 실행한다. sPDF는
가벼운 PDF 보기·편집·OCR 앱으로 유지되며, Paper Organizer를 실행하지 않아도
기존 기능과 시작 성능에 영향이 없다.

Paper Organizer 설정에서 `input`과 `organized` 폴더를 각각 지정할 수 있다.
자동 처리를 켜면 `input`의 영어 논문 PDF를 로컬 Ollama로 분석해 카테고리
폴더로 이동하고, PDF 옆에 `*.pdf.spdf.json` 메타데이터를 저장한다. 화면에서는
카테고리, 제목, 저자, 키워드, 한국어 요약, 기여점과 한계를 구조화해 보여준다.

```bash
ollama pull qwen3:8b
python paper_organizer.py
```

- Ollama는 `http://127.0.0.1:11434`에서 실행되어야 한다.
- `input`과 `organized`는 서로 다른 폴더여야 하며 OneDrive 폴더도 지정할 수 있다.
- 분석에 실패한 PDF는 이동하거나 삭제하지 않고 `input`에 그대로 둔다.
- 텍스트가 거의 없는 스캔 PDF는 먼저 OCR이 필요하다.
- 목록에서 논문을 더블클릭하면 Windows 기본 PDF 앱으로 연다. sPDF를 기본
  PDF 앱으로 지정했다면 sPDF에서 열린다.

## 진행 상황

- [x] **v0.1 뷰어** — 열기(암호 PDF 포함)/썸네일(레이지 렌더)/줌/페이지 이동/드래그&드롭
- [x] **v0.2 텍스트 선택·복사 + 검색** — 드래그/더블클릭/Ctrl+A 선택, Ctrl+C 복사(줄바꿈 복원), Ctrl+F 검색(F3/Shift+F3 이동)
- [x] **v0.3 주석 + 저장 + 최근 파일** — 형광펜(Ctrl+H)/메모(Ctrl+M, 우클릭 메뉴), Ctrl+S 저장(.bak 백업), 저장 안 된 변경 확인, 최근 파일 메뉴(전체 경로 표시)
  - v0.3.2: 메모 호버 툴팁/클릭으로 열기, 메모 모아보기 패널(Ctrl+Shift+M)
- [x] **v0.4 OCR (RapidOCR)** — 현재 페이지(Ctrl+R)/전체 문서(Ctrl+Shift+R) OCR, 한국어+영어, 보이지 않는 텍스트 레이어 삽입 → 스캔본도 검색·복사 가능. 저장하면 검색가능 PDF로 반영
  - v0.4.1: 렌더 배율을 페이지 크기 기준 자동 결정(A4≈6배) — 저해상도 스캔(영수증 등) 인식률 개선
- [x] **v0.5 sPDF 개명 + 시작 페이지 + 즐겨찾기 + 오픈소스 고지** — Acrobat식 홈 화면(열기/즐겨찾기/최근), 즐겨찾기(파일 메뉴 + 홈 우클릭), 도움말→오픈소스 라이선스, LICENSES.md
- [x] **v0.6 텍스트 편집(일반 PDF) + undo/redo** — 편집 모드(Ctrl+E)에서 글자 토막 클릭 → 수정, 실행취소/다시실행(Ctrl+Z / Ctrl+Y, 스냅샷 방식). 한계: 원본 폰트 대신 기본 폰트로 다시 써져 모양이 달라질 수 있고 리플로우 없음(그 줄 안에서만 교체)
- [x] **v0.7 페이지 조작 + 사용법** — 회전(Ctrl+]/[)·삭제(Ctrl+Delete)·순서변경(썸네일 드래그)·여러 PDF 병합·범위별 분리·현재 페이지 추출. 문서 변경은 Ctrl+Z 되돌리기, 분리/추출은 원본을 유지. 도움말→사용법(F1) 다이얼로그
- [x] **v0.8 새 창 + 휠 페이지 넘김 + OCR 품질** — 다른 파일은 새 창으로(Ctrl+N), 휠로 페이지 끝에서 다음/이전 장, OCR 전처리(deskew+sharpen)로 인식률 개선, 텍스트 있는 페이지 중복 OCR 방지
- [x] **v0.9 스캔본 편집** — OCR 후 편집 모드에서 스캔 글자 클릭 → 주변 종이색을 샘플링해 덮고 새 글자 작성(옛 OCR 텍스트도 함께 제거해 검색 오염 방지). 빈 곳 클릭 = 자유 텍스트 박스. 일반 PDF/스캔본 자동 분기
- [x] **v1.0 설치 파일** — PyInstaller 2-실행파일 빌드(GUI + OCR 워커 격리), 아이콘 자동 생성, Inno Setup 설치본, PDF 연결 등록 + 기본 프로그램 확인
- [x] **v1.1 AI 고품질 OCR (PaddleOCR-VL)** — 도구→AI 고품질 OCR 설정에서 엔진 선택. PaddleOCR-VL 1.5(약 1B, transformers+torch)를 "Spotting" 태스크로 돌려 줄 단위 텍스트+좌표 인식, GPU(CUDA)에서 페이지당 수 초. 런타임(pip)·모델(약 2GB, 앱에서 다운로드)은 별도 설치, 미설치면 RapidOCR로 자동 동작
- [x] **v1.2 탭 방식** — 여러 PDF를 한 창의 탭으로(Ctrl+T), 탭별 독립 상태(페이지·편집·검색·OCR), 중복 열기 시 그 탭으로 이동, 탭 순서 드래그, 모두 닫으면 시작 페이지. 창 방식(창마다 문서)에서 전환 — 활성 탭 메뉴바를 셸로 reparent하는 구조라 믹스인은 거의 그대로
- [x] **v1.3 PDF 병합·분리** — 여러 PDF를 현재 문서에 순서대로 삽입하고, 페이지 범위를 그룹별 PDF로 분리하는 도구 보강
- [x] **v1.4 창 간 탭 이동** — 탭을 다른 sPDF 창의 탭 막대나 빈 창으로 드래그해 이동. 별도 실행된 창 사이에서도 미저장 편집 상태와 원래 저장 경로를 유지하고, 마지막 탭을 내보낸 빈 창은 자동으로 닫힘
- [x] **v1.4.1 브라우저 PDF 연결 설정** — Edge·Chrome·Firefox에서 연 PDF를 Windows 기본 PDF 앱(sPDF)으로 넘기는 사용자별 옵션과 상태 표시 추가
- [x] **v1.4.2 OCR 품질 개선** — 저대비 스캔의 국소 명암 보정, 긴 페이지의 겹침 타일 인식, 중앙 여백 기반 2단 조판 분할과 중복 결과 병합으로 작은 글씨 인식 개선
- [x] **v1.5 손 도구 / 텍스트 선택 도구** — 도구 모음과 보기 메뉴에서 상호작용 모드를 선택. 손 도구는 PDF를 클릭한 채 상하좌우로 이동하고, 텍스트 선택 도구는 기존 선택·복사·주석·편집 흐름을 유지
- [x] **v1.5.1 OCR 엔진 명칭 개선** — OCR 설정의 모호한 '기본' 표현을 실제 엔진 이름인 RapidOCR로 통일
- [x] **v1.5.2 Windows 빌드 출력 수정** — 빌드 배치 파일의 한글 인코딩 오해로 깨진 문구와 가짜 명령 오류가 출력되던 문제 해결
- [x] **v1.5.3 즐겨찾기 도구** — 손 도구·텍스트 선택 도구 옆에서 현재 PDF를 바로 즐겨찾기에 추가하거나 해제
- [ ] (예정) AI OCR 옵션 — Claude API (손글씨 등 최후 수단)

## 구조

```
pdfeditor/
  core.py     # PyMuPDF 래핑 — 열기/저장/렌더/텍스트추출/주석 (Qt 비의존)
  viewer.py   # ViewerMixin — 썸네일/메인뷰/줌/페이지 이동
  textsel.py  # TextSelectMixin — 선택/복사/검색
  annots.py   # AnnotMixin — 형광펜/메모/저장/변경 추적
  editing.py  # EditMixin — 텍스트 편집 + 스냅샷 undo/redo
  pages.py    # PagesMixin — 회전/삭제/순서/병합/추출
  help.py     # 사용법 다이얼로그(F1)
  startpage.py# 시작 페이지(홈) — 열기/즐겨찾기/최근
  ocr.py      # OcrMixin + 서브프로세스 워커 (부모는 onnxruntime 미로드)
  ocr_subprocess.py  # OCR 자식 프로세스 (Qt 없이 onnxruntime/torch 실행)
  vl.py       # VL(고품질 AI OCR) 설치 감지/사양 판정/모델 다운로드
  widgets.py  # PageCanvas/PageView, ThumbList
  settings.py # ~/.pdfeditor.json (최근 파일)
  app.py      # MainWindow — 믹스인 조립
  meta.py     # 버전 정보
run.py / run.pyw
register_filetype.py  # 탐색기 연동 (설계 §8)
```
