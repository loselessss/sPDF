"""Read-only policy shared by the PDF model and embedded UI (no Qt imports)."""

from functools import wraps
from inspect import signature


def command_allowed(host, kind):
    editable = not getattr(host, "read_only", False)
    annotations = getattr(host, "annotations_enabled", editable)
    return {"edit": editable, "annotation": annotations,
            "save": editable or annotations,
            "history": editable or annotations}[kind]


def _command(kind):
    def decorate(method):
        @wraps(method)
        def guarded(self, *args, **kwargs):
            if not command_allowed(self, kind):
                return False
            return method(self, *args, **kwargs)
        guarded.requires_editing = True
        guarded.access_kind = kind
        return guarded
    return decorate


annotation_command = _command("annotation")
saving_command = _command("save")
history_command = _command("history")


def editing_command(method):
    """Disable an editing entry point before dialogs, workers or undo changes."""
    return _command("edit")(method)


def document_annotation(method):
    parameters = signature(method)

    @wraps(method)
    def guarded(self, *args, **kwargs):
        self.ensure_annotatable()
        if self.annotation_mode:
            arguments = dict(parameters.bind(self, *args, **kwargs).arguments)
            arguments.pop("self")
            result = self._annotation_store.execute(self._doc, method.__name__, arguments)
        else:
            result = method(self, *args, **kwargs)
        self.invalidate_render()
        return result
    return guarded


def document_write(method):
    """Reject model mutations even when called without the UI."""
    @wraps(method)
    def guarded(self, *args, **kwargs):
        if self.read_only:
            raise PermissionError("This document is open in read-only mode.")
        return method(self, *args, **kwargs)

    return guarded
