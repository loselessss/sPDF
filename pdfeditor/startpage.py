"""시작 페이지 — 문서가 안 열려 있을 때 보이는 홈 화면.

Adobe Acrobat 홈처럼 열기 버튼 + 즐겨찾기 + 최근 파일을 보여준다.
파일 열기/즐겨찾기 저장 로직은 여기 없다 — 시그널만 쏘고 MainWindow가
처리한다.
"""

import os

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QVBoxLayout, QWidget,
)

from . import settings
from .meta import APP_NAME, APP_VERSION


class _FileList(QListWidget):
    """파일 경로 목록 — 항목 클릭으로 열기, 우클릭 메뉴는 StartPage가 단다."""

    open_requested = pyqtSignal(str)

    def __init__(self, empty_text, parent=None):
        super().__init__(parent)
        self._empty_text = empty_text
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.itemClicked.connect(self._on_click)

    def populate(self, paths):
        self.clear()
        if not paths:
            it = QListWidgetItem(self._empty_text)
            it.setFlags(Qt.NoItemFlags)  # 클릭 불가 안내문
            self.addItem(it)
            return
        for p in paths:
            it = QListWidgetItem("%s\n%s" % (os.path.basename(p), os.path.dirname(p)))
            it.setToolTip(p)
            it.setData(Qt.UserRole, p)
            self.addItem(it)

    def path_at(self, pos):
        it = self.itemAt(pos)
        return it.data(Qt.UserRole) if it else None

    def _on_click(self, item):
        p = item.data(Qt.UserRole)
        if p:
            self.open_requested.emit(p)


class StartPage(QWidget):
    open_file = pyqtSignal(str)
    browse = pyqtSignal()
    lists_changed = pyqtSignal()  # 즐겨찾기/최근 목록이 바뀜 (메뉴 갱신용)
    back_to_doc = pyqtSignal()    # 열어둔 문서로 돌아가기

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(48, 36, 48, 36)
        root.setSpacing(12)

        title = QLabel(APP_NAME)
        f = title.font()
        f.setPointSize(28)
        f.setBold(True)
        title.setFont(f)
        ver = QLabel("v%s — PDF 보기 · 주석 · OCR" % APP_VERSION)
        ver.setStyleSheet("color: gray;")

        btn = QPushButton("PDF 열기...")
        btn.setFixedWidth(160)
        btn.clicked.connect(lambda _c=False: self.browse.emit())

        # 문서를 열어둔 채 홈에 온 경우에만 보이는 '돌아가기' 버튼
        self._back_btn = QPushButton("")
        self._back_btn.clicked.connect(lambda _c=False: self.back_to_doc.emit())
        self._back_btn.hide()

        root.addWidget(title)
        root.addWidget(ver)
        root.addSpacing(8)
        row = QHBoxLayout()
        row.addWidget(btn)
        row.addWidget(self._back_btn)
        row.addStretch(1)
        root.addLayout(row)
        root.addSpacing(8)

        cols = QHBoxLayout()
        cols.setSpacing(16)
        self.fav_list = _FileList("(별표한 파일이 없습니다 — 최근 파일에서 우클릭)")
        self.recent_list = _FileList("(최근 연 파일이 없습니다)")
        for label, lst in (("★ 즐겨찾기", self.fav_list), ("최근 파일", self.recent_list)):
            box = QVBoxLayout()
            head = QLabel(label)
            hf = head.font()
            hf.setBold(True)
            head.setFont(hf)
            box.addWidget(head)
            box.addWidget(lst)
            cols.addLayout(box, 1)
        root.addLayout(cols, 1)

        self.fav_list.open_requested.connect(self.open_file)
        self.recent_list.open_requested.connect(self.open_file)
        self.fav_list.customContextMenuRequested.connect(self._fav_menu)
        self.recent_list.customContextMenuRequested.connect(self._recent_menu)

    def refresh(self):
        # 즐겨찾기는 최근에 추가한 것을 위로
        self.fav_list.populate(list(reversed(settings.favorites())))
        self.recent_list.populate(settings.recent_files())

    def set_current_doc(self, name):
        """열려 있는 문서 이름 — None이면 '돌아가기' 버튼을 숨긴다."""
        if name:
            self._back_btn.setText("← %s(으)로 돌아가기" % name)
            self._back_btn.show()
        else:
            self._back_btn.hide()

    # --- 우클릭 메뉴 ---------------------------------------------------

    def _fav_menu(self, pos):
        p = self.fav_list.path_at(pos)
        if not p:
            return
        m = QMenu(self)
        m.addAction("즐겨찾기에서 제거",
                    lambda _c=False: self._unfav(p))
        m.exec_(self.fav_list.mapToGlobal(pos))

    def _recent_menu(self, pos):
        p = self.recent_list.path_at(pos)
        if not p:
            return
        m = QMenu(self)
        if settings.is_favorite(p):
            m.addAction("즐겨찾기에서 제거", lambda _c=False: self._unfav(p))
        else:
            m.addAction("★ 즐겨찾기에 추가", lambda _c=False: self._fav(p))
        m.addAction("최근 목록에서 제거", lambda _c=False: self._unrecent(p))
        m.exec_(self.recent_list.mapToGlobal(pos))

    def _fav(self, p):
        settings.add_favorite(p)
        self.refresh()
        self.lists_changed.emit()

    def _unfav(self, p):
        settings.remove_favorite(p)
        self.refresh()
        self.lists_changed.emit()

    def _unrecent(self, p):
        settings.remove_recent(p)
        self.refresh()
        self.lists_changed.emit()
