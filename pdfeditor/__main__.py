import sys


def main():
    # GUI와 OCR 작업 프로세스가 Windows에서 같은 sPDF 앱으로 인식되도록
    # 어떤 실행 모드에서도 UI/작업 초기화보다 먼저 명시한다.
    from .windows_integration import set_current_process_app_id
    set_current_process_app_id()

    # OCR은 별도 실행 파일(spdf-ocr.exe)이 처리한다 — 같은 프로세스에서
    # Qt와 onnxruntime를 함께 로드하면 DLL 초기화가 깨지기 때문(paths.py).
    # 개발 모드에서 `--ocr-worker`로 직접 호출하는 경우만 지원(테스트용).
    if "--ocr-worker" in sys.argv:
        from .ocr_subprocess import main as ocr_main
        sys.exit(ocr_main())

    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication

    from .app import new_window
    from .meta import APP_NAME, APP_VERSION
    from .paths import app_icon

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    import os
    icon = app_icon()
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))

    # 탐색기 연결 프로그램으로 열릴 때 파일 경로가 인자로 들어온다(설계 §8).
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    new_window(args[0] if args else None)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
