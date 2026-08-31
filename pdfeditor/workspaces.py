"""Standalone reader/editor windows; embedded access policy stays opt-in."""

import os
from contextlib import contextmanager

from .i18n import localize


def workspace_policy(mode, read_only, annotations_enabled):
    if mode not in (None, "reader", "editor"):
        raise ValueError("Unknown workspace mode: %s" % mode)
    if mode == "reader":
        return True, False
    if mode == "editor":
        if read_only:
            raise ValueError("An editor workspace cannot be read-only.")
        return False, True
    return bool(read_only), (not read_only if annotations_enabled is None
                             else bool(annotations_enabled))


class WindowWorkspaceMixin:
    @property
    def workspace_mode(self):
        return self._workspace_mode

    def workspace_title(self):
        from .meta import APP_NAME
        suffix = {"reader": localize("Reader", "읽기"),
                  "editor": localize("Editor", "편집")}.get(self.workspace_mode)
        return "%s — %s" % (APP_NAME, suffix) if suffix else APP_NAME

    def open_editor(self, source=None):
        # Host-owned read-only windows must never expose an editing escape hatch.
        if self.workspace_mode != "reader":
            return None
        from .app import _app_windows, new_window
        if source is None:
            source = self._tabs.currentWidget()
        path = source.doc.path if source is not None and source.doc else None
        for window in _app_windows:
            if (window.workspace_mode == "editor" and
                    window.updates_enabled == self.updates_enabled and path):
                existing = window._find_open_tab(path)
                if existing is not None:
                    window._tabs.setCurrentWidget(existing)
                    window._show_tabs()
                    window.showNormal() if window.isMinimized() else window.show()
                    window.raise_()
                    window.activateWindow()
                    return window
        window = new_window(updates_enabled=self.updates_enabled,
                            workspace_mode="editor")
        if path:
            tab = window.open_in_tab(path)
            tab._pending_view_state = source.capture_view_state()
        return window


@contextmanager
def readers_released_for_save(editor, path):
    """Release our readers' Windows file handles only for an atomic save.

    Never touch embedded viewers or another editor's unsaved document. Runs on
    the GUI thread, without processing events while reader handles are closed.
    Reopen on both success and failure, before a caller displays a save error.
    """
    if getattr(editor._shell, "workspace_mode", None) != "editor":
        yield
        return
    from .app import _app_windows
    from .core import Document
    target = os.path.normcase(os.path.realpath(path))
    suspended = []
    try:
        for window in list(_app_windows):
            if window.workspace_mode != "reader":
                continue
            for index in range(window._tabs.count()):
                tab = window._tabs.widget(index)
                doc = tab.doc
                if (doc is None or getattr(tab, "_closing_doc", False) or
                        os.path.normcase(os.path.realpath(doc.path)) != target):
                    continue
                state = tab.capture_view_state()
                suspended.append((tab, doc.path, doc._password, state))
                stop_rendering = getattr(tab.view, "stop_rendering", None)
                if stop_rendering is not None:
                    stop_rendering()
                doc.close()
                tab.doc = None
        yield
    finally:
        # Open all handles before rebuilding UI, which can display a warning.
        reopened = []
        for tab, original_path, password, state in suspended:
            try:
                doc = Document(original_path, password, read_only=True,
                               annotations_enabled=False)
                reopened.append((tab, doc, original_path, state, None))
            except Exception as error:
                reopened.append((tab, None, original_path, state, error))
        for tab, doc, original_path, state, error in reopened:
            tab._cache.clear()
            tab._reset_textsel()
            tab._reset_annots()
            tab._reset_edit()
            if doc is not None:
                tab._pending_view_state = state
                tab._set_document(doc, original_path)
            else:
                tab.view.clear()
                tab.thumbs.reset_pages(0)
                tab.bookmarks.set_bookmarks([])
                tab._update_title()
                tab.statusBar().showMessage(localize(
                    "Could not refresh the reader. Reopen the file: ",
                    "읽기 창을 새로 고치지 못했습니다. 파일을 다시 여세요: ") + str(error))
