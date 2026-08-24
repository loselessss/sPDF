"""PDF compression dialog and background worker."""

import os

from PyQt5.QtCore import QThread, Qt
from PyQt5.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QLabel,
    QMessageBox, QProgressDialog, QRadioButton, QVBoxLayout,
)

from .compression_core import compress_pdf_bytes
from .filetypes import suggested_pdf_path
from .i18n import localize, tr


class CompressionDialog(QDialog):
    def __init__(self, parent, source_size):
        super().__init__(parent)
        self.setWindowTitle(tr("PDF 용량 줄이기"))
        self.resize(470, 280)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(localize(
            "Choose how much image quality to trade for a smaller PDF.\n"
            "The result is saved as a separate file.",
            "PDF 크기를 줄이기 위해 조정할 이미지 품질을 선택하세요.\n"
            "결과는 별도의 파일로 저장됩니다.")))
        layout.addWidget(QLabel(localize(
            "Current size: %s" % _format_size(source_size),
            "현재 크기: %s" % _format_size(source_size))))
        self._group = QButtonGroup(self)
        choices = (
            ("lossless", "무손실 최적화",
             "화질을 유지하고 중복·미사용 객체와 압축되지 않은 데이터를 정리합니다."),
            ("balanced", "균형 (권장)",
             "고해상도 이미지를 150 DPI, JPEG 품질 75로 조정합니다."),
            ("strong", "강하게 줄이기",
             "고해상도 이미지를 96 DPI, JPEG 품질 55로 조정합니다."),
        )
        for index, (preset, title, detail) in enumerate(choices):
            button = QRadioButton(tr(title))
            button.setProperty("compressionPreset", preset)
            button.setToolTip(tr(detail))
            button.setChecked(preset == "balanced")
            self._group.addButton(button, index)
            layout.addWidget(button)
            description = QLabel(tr(detail))
            description.setWordWrap(True)
            description.setStyleSheet("color: #606060; margin-left: 24px;")
            layout.addWidget(description)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def preset(self):
        button = self._group.checkedButton()
        return str(button.property("compressionPreset"))


class CompressionWorker(QThread):
    def __init__(self, data, output_path, preset, parent=None):
        super().__init__(parent)
        self.data = data
        self.output_path = output_path
        self.preset = preset
        self.output_size = 0
        self.error = None

    def run(self):
        try:
            self.output_size = compress_pdf_bytes(
                self.data, self.output_path, self.preset)
        except Exception as error:
            self.error = error


def compress_document(parent, document):
    if document.password_protected:
        QMessageBox.warning(
            parent, tr("PDF 용량 줄이기"), localize(
                "Size reduction is not available for a password-protected "
                "PDF because its security settings must be preserved.",
                "암호로 보호된 PDF는 보안 설정을 보존해야 하므로 용량 "
                "줄이기를 사용할 수 없습니다."))
        return None
    source_size = _source_size(document.path, 0)
    dialog = CompressionDialog(parent, source_size)
    if dialog.exec_() != QDialog.Accepted:
        return None
    base = os.path.splitext(suggested_pdf_path(document.path))[0]
    suggested = base + "_compressed.pdf"
    output_path, _filter = QFileDialog.getSaveFileName(
        parent, tr("압축한 PDF 저장"), suggested, tr("PDF 파일 (*.pdf)"))
    if not output_path:
        return None
    output_path = suggested_pdf_path(output_path)
    if (document.path and
            os.path.normcase(os.path.abspath(output_path)) ==
            os.path.normcase(os.path.abspath(document.path))):
        QMessageBox.warning(
            parent, tr("PDF 용량 줄이기"), localize(
                "Choose a different file name. Size reduction always keeps "
                "the open original unchanged.",
                "다른 파일 이름을 선택하세요. 용량 줄이기는 현재 열어 둔 "
                "원본을 항상 그대로 보존합니다."))
        return None
    data = document.snapshot()
    source_size = len(data)
    progress = QProgressDialog(
        tr("PDF 용량을 줄이는 중입니다..."), "", 0, 0, parent)
    progress.setWindowTitle(tr("PDF 용량 줄이기"))
    progress.setCancelButton(None)
    progress.setWindowModality(Qt.WindowModal)
    progress.setWindowFlag(Qt.WindowCloseButtonHint, False)
    worker = CompressionWorker(data, output_path, dialog.preset(), progress)
    worker.finished.connect(progress.accept)
    worker.start()
    progress.exec_()
    worker.wait()
    if worker.error is not None:
        QMessageBox.critical(
            parent, tr("용량 줄이기 실패"),
            localize(
                "Could not reduce the PDF size.\n\n%s" % worker.error,
                "PDF 용량을 줄이지 못했습니다.\n\n%s" % worker.error))
        return None
    percent = round(
        (source_size - worker.output_size) * 100 / source_size
    ) if source_size else 0
    QMessageBox.information(
        parent, tr("PDF 용량 줄이기 완료"), localize(
            "Saved: %s\nBefore: %s\nAfter: %s\nSize reduction: %d%%"
            % (output_path, _format_size(source_size),
               _format_size(worker.output_size), percent),
            "저장됨: %s\n변경 전: %s\n변경 후: %s\n용량 감소율: %d%%"
            % (output_path, _format_size(source_size),
               _format_size(worker.output_size), percent)))
    return output_path


def _source_size(path, fallback):
    try:
        return os.path.getsize(path)
    except OSError:
        return int(fallback)


def _format_size(size):
    value = float(max(0, size))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return "%.1f %s" % (value, unit)
        value /= 1024
