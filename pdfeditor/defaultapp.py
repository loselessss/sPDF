"""PDF 기본 프로그램 확인/설정 안내.

Windows 10/11은 보안상 앱이 기본 연결을 강제로 바꾸지 못하게 막아서
(사용자가 설정 화면에서 직접 확인해야 한다), 여기서는 '현재 무엇으로
연결돼 있는지' 확인하고 설정 화면을 열어주는 것까지만 한다.
"""

import subprocess
import sys


def current_pdf_handler():
    """.pdf의 현재 기본 연결 ProgId. 못 읽으면 None."""
    try:
        import winreg
        key = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
               r"\FileExts\.pdf\UserChoice")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, "ProgId")[0]
    except OSError:
        return None


def is_spdf_default():
    h = current_pdf_handler()
    return bool(h and "spdf" in h.lower())


def friendly_handler_name():
    """현재 기본 연결을 사람이 읽을 이름으로 — ProgId에서 앱 이름 추정."""
    h = current_pdf_handler()
    if not h:
        return "확인할 수 없음 (설정에서 직접 확인하세요)"
    if "spdf" in h.lower():
        return "sPDF (이 프로그램)"
    guess = {
        "AcroExch": "Adobe Acrobat/Reader",
        "Acrobat": "Adobe Acrobat",
        "Chrome": "Google Chrome",
        "MSEdgePDF": "Microsoft Edge",
        "FoxitReader": "Foxit Reader",
        "AppX',": "Windows 앱",
    }
    for key, name in guess.items():
        if key.lower() in h.lower():
            return "%s (%s)" % (name, h)
    return h


def open_default_apps_settings():
    """Windows '기본 앱' 설정 화면을 연다 — .pdf 항목으로 바로."""
    try:
        # Win10/11 공통: 파일 형식별 기본 앱 설정 딥링크
        subprocess.Popen(["cmd", "/c", "start", "",
                          "ms-settings:defaultapps"],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except OSError:
        return False
