"""탐색기 '연결 프로그램'에 PDF Editor 등록/해제 (설계 §8).

현재 사용자(HKCU)에만 쓰므로 관리자 권한이 필요 없고, 기본 PDF 뷰어를
빼앗지도 않는다 — 우클릭 '연결 프로그램' 후보로만 나타난다. 기본 앱
지정은 Windows 설정에서 사용자가 직접.

    python register_filetype.py            # 등록
    python register_filetype.py --unregister
"""
import os
import sys
import winreg

PROG_ID = "PDFEditor.Document"
APP_NAME = "PDF Editor"
HERE = os.path.dirname(os.path.abspath(__file__))


def _pythonw():
    """run.pyw를 콘솔 없이 띄울 pythonw.exe 경로."""
    cand = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return cand if os.path.exists(cand) else sys.executable


def register():
    pythonw = _pythonw()
    runpyw = os.path.join(HERE, "run.pyw")
    command = '"%s" "%s" "%%1"' % (pythonw, runpyw)

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Classes\%s" % PROG_ID) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "PDF 문서")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Classes\%s\shell\open\command" % PROG_ID) as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command)

    # .pdf의 '연결 프로그램' 후보 목록(OpenWithProgids)에만 추가 —
    # 기본값을 덮어쓰지 않는다.
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                          r"Software\Classes\.pdf\OpenWithProgids") as k:
        winreg.SetValueEx(k, PROG_ID, 0, winreg.REG_NONE, b"")

    print("등록 완료. 탐색기에서 PDF 우클릭 → '연결 프로그램'에 '%s'가 보입니다." % APP_NAME)
    print("명령:", command)


def unregister():
    for path in (r"Software\Classes\%s\shell\open\command" % PROG_ID,
                 r"Software\Classes\%s\shell\open" % PROG_ID,
                 r"Software\Classes\%s\shell" % PROG_ID,
                 r"Software\Classes\%s" % PROG_ID):
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Classes\.pdf\OpenWithProgids",
                            0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, PROG_ID)
    except FileNotFoundError:
        pass
    print("등록 해제 완료.")


if __name__ == "__main__":
    if "--unregister" in sys.argv:
        unregister()
    else:
        register()
