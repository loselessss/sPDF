"""OCR 워커 실행 파일의 진입점 — PyQt5를 전혀 import하지 않는다.

프로즌 빌드에서 이 파일로 만든 spdf-ocr.exe는 GUI(sPDF.exe)와 별도
폴더/별도 _internal에 놓인다. 그래야 Qt DLL이 onnxruntime 초기화를
깨뜨리는 충돌(dev/frozen 공통)을 피할 수 있다.
"""
from pdfeditor.ocr_subprocess import main

if __name__ == "__main__":
    import sys
    sys.exit(main())
