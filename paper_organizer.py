"""Paper Organizer 독립 실행 프로그램."""

import os
import sys

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices, QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox

from paperorganizer.ui import PaperLibraryPage


def _app_icon():
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", "spdf.ico")


def _open_pdf(path):
    if not os.path.isfile(path) or not QDesktopServices.openUrl(
            QUrl.fromLocalFile(path)):
        QMessageBox.warning(None, "PDF 열기 실패", "파일을 열 수 없습니다:\n%s" % path)


def main():
    app = QApplication(sys.argv)
    icon = _app_icon()
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    page = PaperLibraryPage()
    page.setWindowTitle("Paper Organizer")
    page.resize(1180, 760)
    page.open_pdf.connect(_open_pdf)
    page.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
