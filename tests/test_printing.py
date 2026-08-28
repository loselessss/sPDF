import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pdfeditor.printing import selected_page_indices


class PrintingTests(unittest.TestCase):
    def test_file_menu_has_one_integrated_print_entry(self):
        source = (Path(__file__).resolve().parents[1] / "pdfeditor" / "app.py"
                  ).read_text(encoding="utf-8")
        self.assertIn('"인쇄...", "Ctrl+P", self.print_document', source)
        self.assertNotIn('self._act(m, "인쇄 미리보기..."', source)
        self.assertNotIn('duplex_menu = m.addMenu', source)

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
        importlib.util.find_spec("PyQt5"),
        "PyQt5가 설치된 환경에서 실행",
    )
    def test_print_options_apply_range_reverse_duplex_and_copies(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtPrintSupport import QPrinter
        from pdfeditor.printing import apply_print_options

        class RecordingPrinter:
            def __getattr__(self, name):
                if name.startswith("set"):
                    return lambda *values: setattr(
                        self, name[3:].lower(), values[0] if len(values) == 1
                        else values)
                raise AttributeError(name)

        printer = RecordingPrinter()
        apply_print_options(printer, {
            "mode": "range", "from_page": 2, "to_page": 4,
            "reverse": True, "duplex": "short", "copies": 3,
            "orientation": "landscape",
        })

        self.assertEqual(printer.printrange, QPrinter.PageRange)
        self.assertEqual(printer.fromto, (2, 4))
        self.assertEqual(printer.duplex, QPrinter.DuplexShortSide)
        self.assertEqual(printer.copycount, 3)
        self.assertEqual(printer.orientation, QPrinter.Landscape)

    @unittest.skipUnless(
        importlib.util.find_spec("PyQt5"),
        "PyQt5가 설치된 환경에서 실행",
    )
    def test_new_printer_applies_saved_duplex_mode(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtPrintSupport import QPrinter
        from pdfeditor import settings
        from pdfeditor.printing import PrintMixin

        class RecordingPrinter:
            HighResolution = QPrinter.HighResolution
            DuplexNone = QPrinter.DuplexNone
            DuplexLongSide = QPrinter.DuplexLongSide
            DuplexShortSide = QPrinter.DuplexShortSide

            def __init__(self, mode):
                self.mode = mode
                self.duplex = None

            def setDocName(self, name):
                self.doc_name = name

            def setDuplex(self, duplex):
                self.duplex = duplex

        class FakeHost(PrintMixin):
            class Document:
                path = "duplex-test.pdf"

            doc = Document()

        with mock.patch.object(settings, "print_duplex_mode",
                               return_value="long"), mock.patch(
                                   "PyQt5.QtPrintSupport.QPrinter",
                                   RecordingPrinter):
            printer = FakeHost()._new_printer()
        self.assertEqual(printer.duplex, QPrinter.DuplexLongSide)

    @unittest.skipUnless(
        importlib.util.find_spec("PyQt5"),
        "PyQt5가 설치된 환경에서 실행",
    )
    def test_auto_orientation_follows_selected_document_page(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtPrintSupport import QPrinter
        from PyQt5.QtWidgets import QApplication
        from pdfeditor.printing import PrintMixin

        app = QApplication.instance() or QApplication([])

        class FakeHost(PrintMixin):
            page_index = 1

            class Document:
                page_count = 2
                path = "orientation-test.pdf"

                @staticmethod
                def page_size(index):
                    return (100, 200) if index == 0 else (200, 100)

            doc = Document()

        host = FakeHost()
        printer = host._new_printer()
        host._prepare_print_orientation(printer, {
            "mode": "current", "orientation": "auto",
        })
        self.assertEqual(printer.orientation(), QPrinter.Landscape)
        app.processEvents()

    @unittest.skipUnless(
        importlib.util.find_spec("PyQt5"),
        "PyQt5가 설치된 환경에서 실행",
    )
    def test_integrated_dialog_contains_preview_and_print_options(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtPrintSupport import QPrintPreviewWidget
        from PyQt5.QtWidgets import QApplication, QWidget
        from pdfeditor.printing import PrintMixin, create_print_dialog

        app = QApplication.instance() or QApplication([])

        class FakeHost(QWidget, PrintMixin):
            class Document:
                page_count = 5
                path = "preview-test.pdf"

            doc = Document()
            page_index = 2

            def _paint_document(self, *_args, **_kwargs):
                return True

        host = FakeHost()
        dialog = create_print_dialog(host)
        self.assertIsInstance(dialog.preview, QPrintPreviewWidget)
        self.assertEqual(dialog.preview.objectName(), "printPreviewWidget")
        self.assertIsNotNone(dialog.findChild(QWidget, "printSettingsCard"))
        self.assertIsNotNone(dialog.findChild(QWidget, "printPreviewCard"))
        self.assertEqual(dialog.mode.count(), 3)
        self.assertEqual(dialog.orientation.count(), 3)
        self.assertEqual(dialog.duplex.count(), 3)
        self.assertEqual(dialog.copies.minimum(), 1)
        self.assertEqual(dialog.to_page.maximum(), 5)
        dialog._preview_timer.stop()
        dialog.close()
        host.close()
        app.processEvents()

    @unittest.skipUnless(
        importlib.util.find_spec("PyQt5") and importlib.util.find_spec("fitz"),
        "PyQt5와 PyMuPDF가 설치된 환경에서 실행",
    )
    def test_prints_multiple_pages_through_qt_printer(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        import fitz
        from PyQt5 import QtPrintSupport
        from PyQt5.QtWidgets import QApplication, QDialog, QWidget
        import pdfeditor.printing as printing
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
                @staticmethod
                def options():
                    return {"mode": "all", "duplex": "simplex"}

                def exec_(self):
                    return QDialog.Accepted

            host = FakeHost()
            original_new_printer = host._new_printer

            def output_printer():
                printer = original_new_printer()
                printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
                printer.setOutputFileName(output)
                return printer

            host._new_printer = output_printer
            with mock.patch.object(
                    printing, "create_print_dialog",
                    return_value=FakePrintDialog()):
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
