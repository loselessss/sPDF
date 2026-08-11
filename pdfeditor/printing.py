"""Windows/Qt 인쇄 대화상자를 통한 PDF 문서 인쇄."""

import os


def selected_page_indices(page_count, current_index=0, mode="all",
                          from_page=0, to_page=0, reverse=False):
    """인쇄 대화상자의 1-based 범위를 0-based 페이지 목록으로 바꾼다."""
    if page_count <= 0:
        return []
    if mode == "current":
        pages = [max(0, min(current_index, page_count - 1))]
    elif mode == "range" and from_page > 0 and to_page > 0:
        start = max(1, min(from_page, page_count)) - 1
        end = max(start + 1, min(to_page, page_count))
        pages = list(range(start, end))
    else:
        pages = list(range(page_count))
    return list(reversed(pages)) if reverse else pages


class PrintMixin:
    """DocumentTab에 인쇄 기능을 제공한다."""

    MAX_PRINT_ZOOM = 300.0 / 72.0

    def print_document(self):
        if self.doc is None or self.doc.page_count <= 0:
            return

        from PyQt5.QtCore import QRectF, Qt
        from PyQt5.QtGui import QPainter
        from PyQt5.QtPrintSupport import (
            QAbstractPrintDialog, QPrintDialog, QPrinter,
        )
        from PyQt5.QtWidgets import (
            QApplication, QDialog, QMessageBox, QProgressDialog,
        )

        from .widgets import qimage_from_render

        printer = QPrinter(QPrinter.HighResolution)
        printer.setDocName(os.path.basename(self.doc.path or "sPDF 문서"))
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("인쇄")
        dialog.setMinMax(1, self.doc.page_count)
        dialog.setFromTo(1, self.doc.page_count)
        dialog.setOption(QAbstractPrintDialog.PrintPageRange, True)
        dialog.setOption(QAbstractPrintDialog.PrintCurrentPage, True)
        if dialog.exec_() != QDialog.Accepted:
            return

        print_range = printer.printRange()
        if print_range == QPrinter.CurrentPage:
            mode = "current"
        elif print_range == QPrinter.PageRange:
            mode = "range"
        else:
            mode = "all"
        pages = selected_page_indices(
            self.doc.page_count,
            self.page_index,
            mode,
            printer.fromPage(),
            printer.toPage(),
            printer.pageOrder() == QPrinter.LastPageFirst,
        )
        if not pages:
            return

        progress = QProgressDialog(
            "인쇄용 페이지를 준비하는 중입니다…", "취소",
            0, len(pages), self,
        )
        progress.setWindowTitle("인쇄")
        progress.setMinimumDuration(0)
        progress.setWindowModality(Qt.WindowModal)

        painter = QPainter()
        if not painter.begin(printer):
            progress.close()
            QMessageBox.warning(
                self, "인쇄 실패", "선택한 프린터에서 인쇄를 시작할 수 없습니다.")
            return

        cancelled = False
        error = None
        try:
            printable = QRectF(printer.pageRect(QPrinter.DevicePixel))
            for position, page_index in enumerate(pages):
                if progress.wasCanceled():
                    cancelled = True
                    printer.abort()
                    break
                if position > 0 and not printer.newPage():
                    raise RuntimeError("프린터에서 다음 페이지를 만들 수 없습니다.")

                page_width, page_height = self.doc.page_size(page_index)
                if page_width <= 0 or page_height <= 0:
                    raise RuntimeError(
                        "%d쪽 크기를 읽을 수 없습니다." % (page_index + 1))
                render_zoom = min(
                    self.MAX_PRINT_ZOOM,
                    printable.width() / page_width,
                    printable.height() / page_height,
                )
                image = qimage_from_render(
                    *self.doc.render(page_index, render_zoom))
                image_aspect = image.width() / max(1.0, image.height())
                target_width = printable.width()
                target_height = target_width / image_aspect
                if target_height > printable.height():
                    target_height = printable.height()
                    target_width = target_height * image_aspect
                target = QRectF(
                    printable.center().x() - target_width / 2,
                    printable.center().y() - target_height / 2,
                    target_width,
                    target_height,
                )
                painter.drawImage(target, image)
                progress.setLabelText(
                    "%d쪽 인쇄 준비 중…" % (page_index + 1))
                progress.setValue(position + 1)
                QApplication.processEvents()
        except Exception as exc:  # 프린터/드라이버 오류는 사용자에게 설명한다.
            error = str(exc)
        finally:
            painter.end()
            progress.close()

        if error:
            QMessageBox.warning(self, "인쇄 실패", error)
        elif cancelled:
            self.statusBar().showMessage("인쇄를 취소했습니다", 3000)
        else:
            self.statusBar().showMessage(
                "%d쪽을 프린터로 보냈습니다" % len(pages), 5000)
