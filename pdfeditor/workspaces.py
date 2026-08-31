"""Standalone workspace policy. Embedded access remains explicitly opt-in."""
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

    def open_editor(self, source=None, recovery=False):
        if self.workspace_mode != "reader":
            return None
        from .process_workspace import application_bridge
        try:
            return application_bridge().launch(self, source, recovery=recovery)
        except OSError as error:
            self.statusBar().showMessage(str(error), 8000)
            return None

    def open_reader(self):
        if self.workspace_mode != "editor":
            return None
        from .process_workspace import application_bridge
        try:
            return application_bridge().launch(self, mode="reader")
        except OSError as error:
            self.statusBar().showMessage(str(error), 8000)
            return None
