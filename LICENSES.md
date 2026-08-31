# sPDF licensing and third-party notices / 라이선스·오픈소스 고지

## sPDF

Copyright (c) 2026 loselessss and contributors.

sPDF is free software: you can redistribute it and/or modify it under the
GNU Affero General Public License, version 3 only (`AGPL-3.0-only`).
sPDF is distributed WITHOUT ANY WARRANTY; without even the implied warranty
of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See [LICENSE](LICENSE)
for the complete terms. This declaration applies to the sPDF application,
its OCR worker, and its associated build scripts, tests and documentation.

sPDF는 GNU Affero General Public License 버전 3만(`AGPL-3.0-only`) 적용하여
재배포·수정할 수 있는 자유 소프트웨어입니다. 상품성이나 특정 목적 적합성을
포함하여 어떠한 보증도 제공하지 않습니다. 전체 조건은 [LICENSE](LICENSE)에
있습니다. 이 선언은 sPDF 앱·OCR 워커와 관련 빌드 스크립트·테스트·문서에 적용합니다.

### Previous MIT notice and scope / 기존 MIT 고지와 적용 범위

The previous sPDF MIT notice is preserved verbatim in
[licenses/MIT-sPDF-legacy.txt](licenses/MIT-sPDF-legacy.txt). This change does
not revoke permissions already granted for earlier MIT-licensed sPDF code.
It does not relicense third-party components or grant an MIT-only license
to the combined application containing AGPL/GPL components.

The unrelated project files `paper_organizer.py`, `paper_organizer.pyw`,
`paperorganizer/`, `tests/test_paperlib.py`, `tests/test_paper_settings.py`,
and the reader API guide `docs/READER_INTEGRATION.md` are excluded from this sPDF licensing
change; their previous notices and licensing remain applicable.
Renaming the reader API guide does not change its previous license.
No licensing decision for another repository is made here.

기존 MIT 고지는 위 파일에 그대로 보존하며, 이전 MIT 코드에 이미 부여된 권한을
철회하지 않습니다. AGPL/GPL 구성요소를 포함한 완성 앱 전체를 MIT 조건만으로
배포할 수 있다는 뜻은 아닙니다. 위에 열거한 다른 프로젝트의 파일과 리더 API
문서는 이번 변경에서 제외합니다. 리더 API 문서는 이름 변경 후에도 기존
라이선스를 유지하며, 다른 저장소의 라이선스도 변경하지 않습니다.

## Third-party components / 외부 구성요소

Each component keeps its own copyright and license. The following is an
overview, not a replacement for its full notices. Packaged builds also include
`third-party/` with the actual build-environment versions, metadata and bundled
license/notice files. Optional engines downloaded separately are not covered
by this inventory and must retain their own notices.

각 구성요소의 저작권·라이선스는 그대로 유지됩니다. 아래 표는 요약이며 원문을
대신하지 않습니다. 설치본의 `third-party/`에는 실제 빌드 환경의 버전·메타데이터·
라이선스·고지 사본을 포함합니다. 별도로 다운로드하는 선택형 엔진은 해당 엔진의
라이선스도 확인해야 합니다.

| Component / 구성요소 | License / 라이선스 | Upstream / 원본 |
| --- | --- | --- |
| PyMuPDF / MuPDF | AGPL v3 | [Artifex / PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |
| PyQt5 | GPL v3 | [Riverbank Computing](https://www.riverbankcomputing.com/software/pyqt/) |
| Qt libraries supplied by PyQt5-Qt5 | LGPL v3 / GPL v3, plus component-specific notices | [Qt licensing](https://www.qt.io/licensing/open-source-lgpl-obligations) |
| PyQt5-sip | BSD-style; see packaged version's notice | [SIP](https://github.com/Python-SIP/sip) |
| RapidOCR | Apache 2.0 | [RapidAI](https://github.com/RapidAI/RapidOCR) |
| PaddleOCR recognition models | Apache 2.0 | [PaddlePaddle](https://github.com/PaddlePaddle/PaddleOCR) |
| ONNX Runtime | MIT, with third-party notices | [Microsoft](https://github.com/microsoft/onnxruntime) |
| OpenCV | Apache 2.0, with bundled component notices | [OpenCV](https://github.com/opencv/opencv-python) |
| NumPy | BSD 3-Clause, with bundled component notices | [NumPy](https://numpy.org/) |
| Pillow | HPND-style, with bundled component notices | [Pillow](https://github.com/python-pillow/Pillow) |
| Python runtime | PSF license and included notices | [Python](https://docs.python.org/3/license.html) |
| PyInstaller bootloader | GPL with the PyInstaller distribution exception | [PyInstaller](https://pyinstaller.org/en/stable/license.html) |

Copies of the AGPL, GPL, LGPL and Apache texts are supplied in `LICENSE` and
`licenses/`. The LGPL text includes the GPL text it incorporates. Original
copyright, attribution and NOTICE files must also be retained; copying only
the generic license text does not replace those obligations.

AGPL·GPL·LGPL·Apache 원문은 `LICENSE`와 `licenses/`에 포함합니다. 각 프로젝트의
저작권·출처·NOTICE도 보존해야 하며, 일반 라이선스 원문만 넣는 것으로 이를
대체하지 않습니다.

## Source and redistribution / 소스 제공·재배포

See [SOURCE_CODE.md](SOURCE_CODE.md) for version-matched sources, dependencies
and build instructions. Supplying an executable requires the applicable
corresponding-source access and license notices, not merely a public repository.
If you modify covered software for remote network use, review AGPL section 13.
Embedding sPDF or using read-only mode does not create a licensing exemption.
Ordinary PDF documents processed by sPDF do not become AGPL merely through use.

버전에 맞는 소스·의존성·빌드 안내는 [SOURCE_CODE.md](SOURCE_CODE.md)를 참고하세요.
실행 파일 배포에는 대응 소스 접근과 고지가 필요하며, 저장소 공개만으로 모든
조건을 충족했다고 보지 않습니다. 수정한 프로그램을 네트워크 서비스로 제공할
경우 AGPL 13조도 검토해야 합니다. 내장 모드나 읽기 전용 모드는 라이선스 예외가
아니며, 일반 PDF 문서가 sPDF로 처리되었다는 이유만으로 AGPL이 되지는 않습니다.
