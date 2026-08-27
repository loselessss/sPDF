"""Atomic recovery copies, isolated by process and never written to originals."""

import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid
import zipfile

from PyQt5.QtCore import QLockFile


MAX_RECOVERY_BYTES = 512 * 1024 * 1024
_ID = re.compile(r"^[0-9a-f]{32}$")


class RecoveryStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = self.root / uuid.uuid4().hex
        self.session.mkdir()
        self._locks = {}
        if not self._claim(self.session):
            raise OSError("Could not lock the recovery session.")
        self._guard = threading.RLock()
        self._active = {}

    def _claim(self, folder):
        if folder in self._locks:
            return True
        lock = QLockFile(str(folder / "owner.lock"))
        lock.setStaleLockTime(0)  # A live process never expires by age.
        if not lock.tryLock(0):
            return False
        self._locks[folder] = lock
        return True

    def new_token(self):
        token = uuid.uuid4().hex
        with self._guard:
            self._active[token] = self.session / (token + ".recovery")
        return token

    def adopt(self, entry):
        path = self._checked_path(entry["file"])
        if path.parent not in self._locks:
            raise ValueError("Recovery session is not owned by this process.")
        with self._guard:
            self._active[path.stem] = path
        return path.stem

    def _checked_path(self, path):
        path = Path(path).resolve()
        if (path.parent.parent != self.root or
                not _ID.fullmatch(path.parent.name) or
                not _ID.fullmatch(path.stem) or path.suffix != ".recovery"):
            raise ValueError("Invalid recovery path.")
        return path

    def write(self, token, data, original_path, state):
        if len(data) > MAX_RECOVERY_BYTES:
            raise ValueError("Recovery copy exceeds the 512 MB safety limit.")
        with self._guard:
            destination = self._active.get(token)
        if destination is None:
            return False
        manifest = {"path": str(original_path), "saved_at": time.time(),
                    "view": state}
        fd, temporary = tempfile.mkstemp(dir=destination.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as stream:
                with zipfile.ZipFile(stream, "w", zipfile.ZIP_STORED) as archive:
                    archive.writestr("document.pdf", data)
                    archive.writestr("manifest.json", json.dumps(manifest))
                stream.flush()
                os.fsync(stream.fileno())
            with self._guard:
                if self._active.get(token) != destination:
                    return False
                os.replace(temporary, destination)
            return True
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    def discard(self, token):
        with self._guard:
            path = self._active.pop(token, None)
            if path is not None:
                path.unlink(missing_ok=True)

    def discard_entry(self, entry):
        path = self._checked_path(entry["file"])
        if path.parent not in self._locks:
            raise ValueError("Recovery session is not owned by this process.")
        path.unlink(missing_ok=True)

    def available(self):
        entries = []
        for folder in self.root.iterdir():
            if (not folder.is_dir() or not _ID.fullmatch(folder.name) or
                    folder == self.session or not self._claim(folder)):
                continue
            for path in folder.glob("*.recovery"):
                if path.stem in self._active:
                    continue
                try:
                    self._checked_path(path)
                    with zipfile.ZipFile(path) as archive:
                        if archive.getinfo("manifest.json").file_size > 65536:
                            continue
                        if archive.getinfo("document.pdf").file_size > MAX_RECOVERY_BYTES:
                            continue
                        entry = json.loads(archive.read("manifest.json"))
                    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                        continue
                    stamp = float(entry.get("saved_at", 0))
                    if not math.isfinite(stamp) or not 0 <= stamp <= 32503680000:
                        continue
                    entry["saved_at"] = stamp
                    entry["file"] = str(path)
                    entries.append(entry)
                except (OSError, TypeError, ValueError, KeyError, zipfile.BadZipFile):
                    continue
        return sorted(entries, key=lambda e: float(e.get("saved_at", 0)), reverse=True)

    def read(self, entry):
        path = self._checked_path(entry["file"])
        if path.parent not in self._locks:
            raise ValueError("Recovery session is not owned by this process.")
        with zipfile.ZipFile(path) as archive:
            if archive.getinfo("document.pdf").file_size > MAX_RECOVERY_BYTES:
                raise ValueError("Recovery copy is too large.")
            return archive.read("document.pdf")
