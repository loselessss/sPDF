"""Recovery timers and explicit restore/discard UI for standalone sPDF."""

import os
import threading
from datetime import datetime

from PyQt5.QtCore import QObject, QTimer, Qt
from PyQt5.QtWidgets import (
    QApplication, QAbstractItemView, QDialog, QDialogButtonBox, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout,
)

from .i18n import localize, tr
from .paths import user_data_dir
from .recovery import MAX_RECOVERY_BYTES, RecoveryStore


def application_recovery_store():
    application = QApplication.instance()
    store = getattr(application, "_spdf_recovery_store", None)
    if store is None:
        store = RecoveryStore(os.path.join(user_data_dir(), "recovery"))
        application._spdf_recovery_store = store
    return store


class TabRecovery(QObject):
    def __init__(self, tab, store):
        super().__init__(tab)
        self.tab, self.store = tab, store
        self.token = None
        self.revision = 0
        self.saved_revision = -1
        self.worker = None
        self.error = None
        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.checkpoint)

    def changed(self):
        self.revision += 1
        if self.store is not None and not self.timer.isActive():
            self.timer.start()

    def adopt(self, entry):
        self.token = self.store.adopt(entry)

    def checkpoint(self):
        tab = self.tab
        if self.store is None or tab.doc is None or not tab._dirty:
            return
        if self.worker is not None and self.worker.is_alive():
            return
        if self.error is not None:
            tab.statusBar().showMessage(localize(
                "Recovery copy could not be saved; save your work manually.",
                "복구용 사본을 저장하지 못했습니다. 작업을 직접 저장하세요."), 8000)
            self.error = None
        if self.saved_revision == self.revision:
            return
        if tab.doc.password_protected:
            self.timer.stop()
            tab.statusBar().showMessage(localize(
                "Automatic recovery is disabled for protected PDFs. Save manually.",
                "보호된 PDF는 자동 복구 사본을 만들지 않습니다. 직접 저장하세요."), 8000)
            return
        try:
            if (os.path.exists(tab.doc.path) and
                    os.path.getsize(tab.doc.path) > MAX_RECOVERY_BYTES):
                self._too_large()
                return
            data = tab.doc.snapshot()
            if len(data) > MAX_RECOVERY_BYTES:
                self._too_large()
                return
            state = tab.capture_view_state()
        except Exception as error:
            self.error = error
            return
        if self.token is None:
            self.token = self.store.new_token()
        token, revision, path = self.token, self.revision, tab.doc.path

        def write():
            try:
                if self.store.write(token, data, path, state):
                    self.saved_revision = revision
            except Exception as error:
                self.error = error

        # Only immutable bytes are used here: no Qt or shared MuPDF access.
        # Close never waits for this thread; invalidated tokens cannot reappear.
        self.worker = threading.Thread(target=write, daemon=True)
        self.worker.start()

    def _too_large(self):
        self.timer.stop()
        self.tab.statusBar().showMessage(localize(
            "Automatic recovery is limited to 512 MB per document. Save manually.",
            "자동 복구는 문서당 512 MB까지 지원합니다. 직접 저장하세요."), 8000)

    def clear(self):
        self.timer.stop()
        if self.token is not None:
            try:
                self.store.discard(self.token)
            except OSError:
                pass
            self.token = None
        self.saved_revision = -1


def show_recovery_dialog(shell, automatic=False):
    store = shell._recovery_store
    if store is None:
        return
    try:
        entries = store.available()
    except OSError as error:
        QMessageBox.warning(shell, tr("미저장 작업 복구"), str(error))
        return
    if not entries:
        if not automatic:
            QMessageBox.information(shell, tr("미저장 작업 복구"), localize(
                "There are no recovery copies from interrupted sessions.",
                "이전 실행에서 남은 복구용 사본이 없습니다."))
        return
    dialog = QDialog(shell)
    dialog.setWindowTitle(tr("미저장 작업 복구"))
    dialog.resize(620, 380)
    layout = QVBoxLayout(dialog)
    label = QLabel(localize(
        "Recovery copies from an interrupted session were found.\n"
        "Restore selected files, discard their copies, or decide later.\n"
        "Recovered documents use Save As to protect the originals.",
        "이전 실행에서 남은 복구용 사본이 있습니다.\n"
        "선택한 파일을 복구하거나 사본을 삭제할 수 있습니다. 취소하면 보관합니다.\n"
        "복구한 문서는 원본 보호를 위해 다른 이름으로 저장합니다."))
    label.setWordWrap(True)
    layout.addWidget(label)
    listing = QListWidget()
    listing.setSelectionMode(QAbstractItemView.ExtendedSelection)
    for entry in entries:
        stamp = datetime.fromtimestamp(entry["saved_at"]).strftime("%Y-%m-%d %H:%M")
        item = QListWidgetItem("%s — %s\n%s" % (
            os.path.basename(entry["path"]), stamp, entry["path"]))
        item.setData(Qt.UserRole, entry)
        listing.addItem(item)
        item.setSelected(True)
    layout.addWidget(listing)
    buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
    recover = buttons.addButton(tr("선택한 작업 복구"), QDialogButtonBox.AcceptRole)
    discard = buttons.addButton(tr("선택한 사본 삭제"), QDialogButtonBox.DestructiveRole)
    buttons.rejected.connect(dialog.reject)
    recover.clicked.connect(dialog.accept)
    discard.clicked.connect(lambda: dialog.done(2))
    layout.addWidget(buttons)
    result = dialog.exec_()
    if result not in (QDialog.Accepted, 2):
        return
    for item in listing.selectedItems():
        entry = item.data(Qt.UserRole)
        tab = None
        try:
            if result == 2:
                store.discard_entry(entry)
                continue
            if shell._find_open_tab(entry["path"]) is not None:
                QMessageBox.information(shell, tr("미저장 작업 복구"), localize(
                    "Close the already-open original tab before recovering:\n%s",
                    "이미 열린 원본 탭을 닫은 뒤 복구하세요:\n%s") % entry["path"])
                continue
            from .app import DocumentTab
            tab = DocumentTab(shell)
            shell._connect_tab(tab)
            index = shell._tabs.addTab(tab, tr("불러오는 중..."))
            shell._tabs.setCurrentIndex(index)
            shell._show_tabs()
            if not tab.open_snapshot(store.read(entry), entry["path"]):
                shell._remove_tab(tab)
                continue
            tab._recovery.adopt(entry)
            tab._recovered_unsaved = True
            from .settings import _clean_reading_position
            tab._initial_reading_state = _clean_reading_position(entry.get("view"))
        except Exception as error:
            if tab is not None and tab.doc is None:
                shell._remove_tab(tab)
            QMessageBox.warning(shell, tr("미저장 작업 복구"), str(error))
