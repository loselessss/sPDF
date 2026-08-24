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

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication

    from .app import new_window
    from .meta import APP_NAME, APP_VERSION
    from .paths import app_icon
    from .theme import apply_fluent_theme

    # Windows의 모든 Qt 대화상자 제목 표시줄에 자동으로 붙는 `?`
    # 컨텍스트 도움말 버튼을 앱 전체에서 제거한다.
    QApplication.setAttribute(Qt.AA_DisableWindowContextHelpButton, True)
    # 국제판은 Qt 자체 대화상자도 영어 번역 계층을 통과해야 하므로 운영체제의
    # 한국어 네이티브 파일 대화상자 대신 Qt 대화상자를 사용한다.
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_NAME)
    from .i18n import install as install_i18n
    install_i18n(app)
    apply_fluent_theme(app)
    import os
    icon = app_icon()
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))

    # 탐색기 연결 프로그램으로 열릴 때 파일 경로가 인자로 들어온다(설계 §8).
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    # 공식 실행 진입점에서만 자체 업데이트를 켠다. 다른 프로그램이
    # pdfeditor를 내부 모듈로 불러 new_window/AppWindow를 만들면 기본값은 꺼짐이다.
    new_window(args[0] if args else None, updates_enabled=True)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
