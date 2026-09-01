"""Standalone editing helpers shared with the separate page organizer."""

from PyQt5.QtWidgets import QPushButton

from .i18n import localize
from .icons import fluent_icon


class EditorWorkspaceMixin:
    def _init_editor_workspace(self, viewer):
        self._page_grid = None
        self._workspace_header = None
        self._editor_overview = False
        return viewer

    def add_editor_mode_button(self, tool_bar):
        self._editor_mode_button = self._mode_button(
            localize("Edit mode", "편집 모드"), "edit", accent=True)
        self._editor_mode_button.setObjectName("openEditorModeButton")
        self._editor_mode_button.setToolTip(localize(
            "Open the page organizer in an editor window (Ctrl+E)",
            "편집 창의 페이지 구성으로 열기 (Ctrl+E)"))
        self._editor_mode_button.clicked.connect(lambda: self._shell.open_editor(self))
        tool_bar.addWidget(self._editor_mode_button)
        tool_bar.addSeparator()

    @staticmethod
    def _mode_button(text, icon, *, accent=False):
        button = QPushButton(text)
        button.setMinimumSize(145, 40)
        button.setProperty("accent", accent)
        button.setStyleSheet("font-size: 14px; font-weight: 600;")
        button.setIcon(fluent_icon(icon, "#ffffff" if accent else "#242424"))
        return button

    def is_editor_overview(self):
        return False

    def _select_overview_page(self, row):
        pass

    def refresh_editor_overview(self, *, reset=False):
        pass

    def show_editor_overview(self):
        self.show_page_organizer()

    def open_page_editor(self, page=None, *, edit_text=True):
        if self._shell.workspace_mode != "editor" or self.doc is None:
            return
        page = self.page_index if page is None else int(page)
        page = max(0, min(page, self.doc.page_count - 1))
        self._editor_overview = False
        self._two_page_mode = False
        self._two_page_act.setChecked(False)
        self._set_fit_zoom(page)
        self.show_page(page)
        self.set_edit_mode(edit_text)
        self._sync_editor_workspace_actions()
        self._schedule_thumbs()
        self.view.setFocus()

    def _sync_editor_workspace_actions(self):
        if hasattr(self, "_pages_act"):
            self._pages_act.setCheckable(False)
            self._pages_act.setToolTip(localize(
                "Open page organization in a separate window (Ctrl+Shift+P)",
                "페이지 구성을 별도 창으로 열기 (Ctrl+Shift+P)"))
        if hasattr(self, "_zoom_input"):
            self._zoom_input.setVisible(True)
