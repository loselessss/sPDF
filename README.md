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
않음 — 도움말 → **PDF 기본 프로그램 확인**에서 현재 상태 확인/설정 열기).

## 탐색기에서 열기 (설치 없이, 개발용)

```bash
python register_filetype.py              # 등록
python register_filetype.py --unregister # 해제
```

## 진행 상황

- [x] **v0.1 뷰어** — 열기(암호 PDF 포함)/썸네일(레이지 렌더)/줌/페이지 이동/드래그&드롭
- [x] **v0.2 텍스트 선택·복사 + 검색** — 드래그/더블클릭/Ctrl+A 선택, Ctrl+C 복사(줄바꿈 복원), Ctrl+F 검색(F3/Shift+F3 이동)
- [x] **v0.3 주석 + 저장 + 최근 파일** — 형광펜(Ctrl+H)/메모(Ctrl+M, 우클릭 메뉴), Ctrl+S 저장(.bak 백업), 저장 안 된 변경 확인, 최근 파일 메뉴(전체 경로 표시)
  - v0.3.2: 메모 호버 툴팁/클릭으로 열기, 메모 모아보기 패널(Ctrl+Shift+M)
- [x] **v0.4 OCR (RapidOCR)** — 현재 페이지(Ctrl+R)/전체 문서(Ctrl+Shift+R) OCR, 한국어+영어, 보이지 않는 텍스트 레이어 삽입 → 스캔본도 검색·복사 가능. 저장하면 검색가능 PDF로 반영
  - v0.4.1: 렌더 배율을 페이지 크기 기준 자동 결정(A4≈6배) — 저해상도 스캔(영수증 등) 인식률 개선
- [x] **v0.5 sPDF 개명 + 시작 페이지 + 즐겨찾기 + 오픈소스 고지** — Acrobat식 홈 화면(열기/즐겨찾기/최근), 즐겨찾기(파일 메뉴 + 홈 우클릭), 도움말→오픈소스 라이선스, LICENSES.md
- [x] **v0.6 텍스트 편집(일반 PDF) + undo/redo** — 편집 모드(Ctrl+E)에서 글자 토막 클릭 → 수정, 실행취소/다시실행(Ctrl+Z / Ctrl+Y, 스냅샷 방식). 한계: 원본 폰트 대신 기본 폰트로 다시 써져 모양이 달라질 수 있고 리플로우 없음(그 줄 안에서만 교체)
- [x] **v0.7 페이지 조작 + 사용법** — 회전(Ctrl+]/[)·삭제(Ctrl+Delete)·순서변경(썸네일 드래그)·병합·추출, 모두 Ctrl+Z 되돌리기. 도움말→사용법(F1) 다이얼로그
- [x] **v0.8 새 창 + 휠 페이지 넘김 + OCR 품질** — 다른 파일은 새 창으로(Ctrl+N), 휠로 페이지 끝에서 다음/이전 장, OCR 전처리(deskew+sharpen)로 인식률 개선, 텍스트 있는 페이지 중복 OCR 방지
- [x] **v0.9 스캔본 편집** — OCR 후 편집 모드에서 스캔 글자 클릭 → 주변 종이색을 샘플링해 덮고 새 글자 작성(옛 OCR 텍스트도 함께 제거해 검색 오염 방지). 빈 곳 클릭 = 자유 텍스트 박스. 일반 PDF/스캔본 자동 분기
- [x] **v1.0 설치 파일** — PyInstaller 2-실행파일 빌드(GUI + OCR 워커 격리), 아이콘 자동 생성, Inno Setup 설치본, PDF 연결 등록 + 기본 프로그램 확인
- [ ] (예정) AI OCR 옵션 (PaddleOCR-VL, Claude API)
- [ ] (예정) OCR 품질 추가 개선 — 저해상도/2단 조판 논문

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
  ocr_subprocess.py  # OCR 자식 프로세스 (Qt 없이 onnxruntime 실행)
  widgets.py  # PageCanvas/PageView, ThumbList
  settings.py # ~/.pdfeditor.json (최근 파일)
  app.py      # MainWindow — 믹스인 조립
  meta.py     # 버전 정보
run.py / run.pyw
register_filetype.py  # 탐색기 연동 (설계 §8)
```
