import importlib.util
import os
import tempfile
import unittest
from unittest import mock

from pdfeditor.printing import selected_page_indices


class PrintingTests(unittest.TestCase):
    def test_all_pages_are_zero_based(self):
        self.assertEqual(selected_page_indices(4), [0, 1, 2, 3])

    def test_current_page_is_clamped(self):
        self.assertEqual(
            selected_page_indices(4, current_index=9, mode="current"), [3])

    def test_dialog_page_range_is_inclusive(self):
        self.assertEqual(
            selected_page_indices(
                8, mode="range", from_page=3, to_page=6),
            [2, 3, 4, 5],
        )

    def test_last_page_first_reverses_selected_range(self):
        self.assertEqual(
            selected_page_indices(
                8, mode="range", from_page=3, to_page=5, reverse=True),
            [4, 3, 2],
        )

    @unittest.skipUnless(
        importlib.util.find_spec("PyQt5") and importlib.util.find_spec("fitz"),
        "PyQt5와 PyMuPDF가 설치된 환경에서 실행",
    )
    def test_prints_multiple_pages_through_qt_printer(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import fitz
        from PyQt5 import QtPrintSupport
        from PyQt5.QtWidgets import QApplication, QDialog, QWidget
        from pdfeditor.printing import PrintMixin

        app = QApplication.instance() or QApplication([])

        class FakeDocument:
            page_count = 2
            path = "print-test.pdf"

            @staticmethod
            def page_size(_index):
                return 100.0, 120.0

            @staticmethod
            def render(_index, zoom):
                width = max(1, round(100 * zoom))
                height = max(1, round(120 * zoom))
                stride = width * 3
                return width, height, stride, bytes([255]) * stride * height

        class FakeStatusBar:
            def showMessage(self, *_args):
                pass

        class FakeHost(QWidget, PrintMixin):
            def __init__(self):
                super().__init__()
                self.doc = FakeDocument()
                self.page_index = 0
                self._status_bar = FakeStatusBar()

            def statusBar(self):
                return self._status_bar

        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "printed.pdf")

            class FakePrintDialog:
                def __init__(self, printer, _parent):
                    printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
                    printer.setOutputFileName(output)

                def setWindowTitle(self, _title):
                    pass

                def setMinMax(self, _minimum, _maximum):
                    pass

                def setFromTo(self, _first, _last):
                    pass

                def setOption(self, _option, _enabled=True):
                    pass

                def exec_(self):
                    return QDialog.Accepted

            host = FakeHost()
            with mock.patch.object(
                    QtPrintSupport, "QPrintDialog", FakePrintDialog):
                host.print_document()
            app.processEvents()
            host.close()

            printed = fitz.open(output)
            try:
                self.assertEqual(printed.page_count, 2)
            finally:
                printed.close()


if __name__ == "__main__":
    unittest.main()
