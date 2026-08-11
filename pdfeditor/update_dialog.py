"""GitHub Releases 업데이트 확인 및 다운로드 UI."""

from pathlib import Path
from threading import Event

from PyQt5.QtCore import QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTextBrowser, QVBoxLayout,
)

from .icons import fluent_icon

def _size_text(size):
    return "%.1f MB" % (size / (1024 * 1024)) if size > 0 else "크기 정보 없음"


class UpdateCheckWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._service = service

    def run(self):
        try:
            self.completed.emit(self._service.check())
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDownloadWorker(QThread):
    progress = pyqtSignal(object)
    completed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, service, update, parent=None):
        super().__init__(parent)
        self._service = service
        self._update = update
        self._cancel = Event()

    def request_cancel(self):
        self._cancel.set()

    def run(self):
        try:
            path = self._service.download(
                self._update, progress=self.progress.emit, cancel=self._cancel)
            self.completed.emit(str(path))
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDialog(QDialog):
    install_requested = pyqtSignal(object)

    def __init__(self, service, update, parent=None):
        super().__init__(parent)
        self._service = service
        self._update = update
        self._worker = None
        self.setWindowTitle("sPDF 업데이트")
        self.setMinimumSize(600, 450)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "<h3>sPDF %s 업데이트가 있습니다.</h3>" % update.version))
        form = QFormLayout()
        form.addRow("현재 버전", QLabel(service.current_version))
        form.addRow("새 버전", QLabel(update.version))
        form.addRow("설치 파일", QLabel(
            "%s (%s)" % (update.asset.name, _size_text(update.asset.size))
            if update.asset else "등록 대기 중"))
        layout.addLayout(form)
        layout.addWidget(QLabel("변경 내용"))
        self.notes = QTextBrowser()
        self.notes.setPlainText(update.release_notes or "변경 기록이 없습니다.")
        layout.addWidget(self.notes, 1)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("나중에")
        buttons.button(QDialogButtonBox.Close).setIcon(fluent_icon("close"))
        buttons.rejected.connect(self.reject)
        self.release_button = QPushButton("릴리스 페이지")
        self.release_button.setIcon(fluent_icon("external"))
        self.release_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(update.release_url)))
        buttons.addButton(self.release_button, QDialogButtonBox.ActionRole)
        self.install_button = QPushButton("다운로드 후 설치")
        self.install_button.setProperty("accent", True)
        self.install_button.setIcon(fluent_icon("download", "#ffffff"))
        self.install_button.clicked.connect(self._start_download)
        buttons.addButton(self.install_button, QDialogButtonBox.AcceptRole)
        layout.addWidget(buttons)

        if update.asset is None:
            self.install_button.setEnabled(False)
            self.status.setText("이 릴리스에는 아직 Windows 설치 파일이 없습니다.")
        elif not update.asset.sha256:
            self.install_button.setEnabled(False)
            self.status.setText(
                "설치 파일 무결성 정보가 없어 앱 안에서는 자동 설치하지 않습니다.")

    def _start_download(self):
        if self._worker is not None:
            return
        self.install_button.setEnabled(False)
        self.release_button.setEnabled(False)
        self.progress.show()
        self.status.setText("업데이트 설치 파일을 다운로드하는 중입니다…")
        worker = UpdateDownloadWorker(self._service, self._update, self)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        self._worker = worker
        worker.start()

    def _on_progress(self, value):
        if value.total_bytes:
            self.progress.setRange(0, 100)
            self.progress.setValue(min(
                100, round(value.completed_bytes * 100 / value.total_bytes)))
        else:
            self.progress.setRange(0, 0)
        speed = value.bytes_per_second / (1024 * 1024)
        self.status.setText(
            "%.1f MB / %s · %.1f MB/s" %
            (value.completed_bytes / (1024 * 1024),
             _size_text(value.total_bytes), speed))

    def _on_completed(self, path):
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.status.setText("다운로드와 SHA-256 검증을 마쳤습니다.")
        self.install_requested.emit(Path(path))
        self.accept()

    def _on_failed(self, message):
        self.status.setText(message)
        if "취소" not in message:
            QMessageBox.warning(self, "업데이트 다운로드 실패", message)

    def _on_finished(self):
        worker = self._worker
        self._worker = None
        if worker:
            worker.deleteLater()
        self.release_button.setEnabled(True)
        if self._update.asset and self._update.asset.sha256:
            self.install_button.setEnabled(True)

    def reject(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self.status.setText("다운로드를 취소하는 중입니다…")
            return
        super().reject()
