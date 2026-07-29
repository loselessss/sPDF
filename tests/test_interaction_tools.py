import importlib.util
import os
import unittest


HAS_PYQT5 = importlib.util.find_spec("PyQt5") is not None


@unittest.skipUnless(HAS_PYQT5, "PyQt5가 설치된 환경에서 실행")
class InteractionToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt5.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_cursor_tracks_selected_interaction_mode(self):
        from PyQt5.QtCore import Qt
        from pdfeditor.widgets import PageView

        view = PageView()
        self.assertEqual(view.canvas.cursor().shape(), Qt.IBeamCursor)
        view.set_interaction_mode("hand")
        self.assertEqual(view.canvas.interaction_mode, "hand")
        self.assertEqual(view.canvas.cursor().shape(), Qt.OpenHandCursor)
        view.set_interaction_mode("select")
        self.assertEqual(view.canvas.cursor().shape(), Qt.IBeamCursor)
        with self.assertRaises(ValueError):
            view.set_interaction_mode("unknown")
        view.close()

    def test_hand_drag_delta_moves_scrollbars_in_opposite_direction(self):
        from PyQt5.QtCore import QPoint
        from pdfeditor.widgets import PageView

        view = PageView()
        view.resize(240, 240)
        view.canvas.resize(1000, 1000)
        view.show()
        self.app.processEvents()
        hbar = view.horizontalScrollBar()
        vbar = view.verticalScrollBar()
        hbar.setValue(200)
        vbar.setValue(200)
        view._pan_canvas(QPoint(25, -30))
        self.assertEqual(hbar.value(), 175)
        self.assertEqual(vbar.value(), 230)
        view.close()

    def test_hidpi_render_keeps_logical_page_size(self):
        from pdfeditor.widgets import PageCanvas, qimage_from_render

        image = qimage_from_render(
            4,
            4,
            12,
            bytes([255] * 48),
            device_pixel_ratio=2.0,
        )
        canvas = PageCanvas()
        canvas.set_image(image, 1.0)

        self.assertEqual(image.devicePixelRatio(), 2.0)
        self.assertEqual(canvas.width(), 2)
        self.assertEqual(canvas.height(), 2)
        canvas.close()


if __name__ == "__main__":
    unittest.main()
