"""Crash-released writer locks and atomic backups (no Qt dependency)."""
from contextlib import contextmanager
import os
import shutil
import tempfile


@contextmanager
def destination_lock(path):
    # Keep the small lock inode: unlinking it permits two simultaneous owners.
    stream = open(os.path.realpath(path) + ".spdf-save.lock", "a+b")
    locked = False
    try:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def atomic_backup(path):
    fd, temporary = tempfile.mkstemp(prefix=".spdf-backup-", dir=os.path.dirname(os.path.abspath(path)))
    try:
        with os.fdopen(fd, "wb") as output, open(path, "rb") as source:
            shutil.copyfileobj(source, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path + ".bak")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
