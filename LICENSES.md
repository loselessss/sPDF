# sPDF 오픈소스 고지

sPDF는 아래 오픈소스 소프트웨어를 사용합니다. 각 구성요소의 저작권은
해당 프로젝트에 있으며, 전체 라이선스 원문은 링크에서 확인할 수 있습니다.

| 구성요소 | 용도 | 라이선스 | 출처 |
|---|---|---|---|
| PyQt5 | GUI 프레임워크 | GPL v3 | https://www.riverbankcomputing.com/software/pyqt/ |
| PyMuPDF (MuPDF) | PDF 렌더링·편집 | AGPL 3.0 | https://github.com/pymupdf/PyMuPDF |
| RapidOCR | OCR 실행 프레임워크 | Apache 2.0 | https://github.com/RapidAI/RapidOCR |
| PaddleOCR 인식 모델 | 한국어/영어 문자 인식 모델 | Apache 2.0 | https://github.com/PaddlePaddle/PaddleOCR |
| ONNX Runtime | 모델 추론 엔진 | MIT | https://github.com/microsoft/onnxruntime |
| NumPy | 이미지 배열 처리 | BSD 3-Clause | https://numpy.org |

## 배포 시 유의사항

개인 사용에는 제약이 없다. 단, 이 프로그램(또는 설치본)을 **외부에
배포**하는 경우:

- **PyQt5 (GPL v3)**: 프로그램 전체 소스 공개 의무 발생 (또는 Riverbank
  상용 라이선스 구매)
- **PyMuPDF (AGPL 3.0)**: 마찬가지로 소스 공개 의무 발생 (또는 Artifex
  상용 라이선스 구매)
- 소스를 공개(GPL/AGPL 호환 라이선스로 배포)한다면 두 조건 모두 충족 가능
- Apache 2.0 / MIT / BSD 구성요소는 고지문 포함으로 충분
