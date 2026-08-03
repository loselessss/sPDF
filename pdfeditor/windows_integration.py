"""Windows에서 sPDF 프로세스를 하나의 데스크톱 앱으로 식별한다."""

import sys


APP_USER_MODEL_ID = "sPDF.Desktop"


def set_current_process_app_id():
    """작업 표시줄과 Windows 셸에 사용할 명시적 앱 ID를 설정한다.

    다른 운영체제와 오래된 Windows에서도 앱 시작을 막지 않도록 실패는
    조용히 무시한다. UI를 만들기 전에 호출해야 창마다 같은 ID가 적용된다.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        setter = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        result = setter(APP_USER_MODEL_ID)
        return result >= 0
    except (AttributeError, OSError):
        return False
