import os
import unittest

from PyQt5 import sip
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget

from pdfeditor.i18n import install, set_language


class TranslationLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.translator = install(cls.app, "en")

    def setUp(self):
        set_language("en")

    def test_polish_translation_waits_for_completed_construction(self):
        button = QPushButton("저장")
        self.translator.eventFilter(button, QEvent(QEvent.Polish))
        self.assertEqual(button.text(), "저장")
        self.app.processEvents()
        self.assertEqual(button.text(), "Save")
        sip.delete(button)

    def test_child_added_never_dereferences_incomplete_child(self):
        class ConstructionEvent:
            def type(self):
                return QEvent.ChildAdded

            def child(self):
                raise AssertionError("Never retain an incomplete child wrapper")

        parent = QWidget()
        self.translator.eventFilter(parent, ConstructionEvent())
        child = QPushButton("저장", parent)
        self.app.processEvents()
        self.assertEqual(child.text(), "Save")
        sip.delete(parent)

    def test_deleted_widget_is_not_read_by_deferred_translation(self):
        button = QPushButton("저장")
        self.translator.schedule(button)
        sip.delete(button)
        self.app.processEvents()
        self.assertTrue(sip.isdeleted(button))

    def test_retranslation_uses_original_source_text(self):
        button = QPushButton("저장")
        self.translator.schedule(button)
        self.app.processEvents()
        self.assertEqual(button.text(), "Save")
        set_language("ko")
        self.translator.schedule(button)
        self.app.processEvents()
        self.assertEqual(button.text(), "저장")
        set_language("en")
        self.translator.schedule(button)
        self.app.processEvents()
        self.assertEqual(button.text(), "Save")
        sip.delete(button)


if __name__ == "__main__":
    unittest.main()
