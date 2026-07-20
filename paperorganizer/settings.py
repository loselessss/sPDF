"""Paper Organizer 전용 설정 — sPDF 본체 설정과 분리한다."""

import json
import os
import tempfile


PATH = os.path.expanduser("~/.spdf-paper-organizer.json")


def _load():
    try:
        with open(PATH, encoding="utf-8") as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data):
    folder = os.path.dirname(PATH) or "."
    os.makedirs(folder, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix=".paper-settings-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temp_path, PATH)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def paper_input_dir():
    return _load().get("input_dir", "")


def paper_organized_dir():
    return _load().get("organized_dir", "")


def paper_model():
    return _load().get("model", "qwen3:8b")


def paper_auto_enabled():
    return bool(_load().get("auto_enabled", False))


def set_paper_settings(input_dir, organized_dir, model, auto_enabled):
    data = _load()
    data.update({
        "input_dir": os.path.abspath(input_dir) if input_dir else "",
        "organized_dir": os.path.abspath(organized_dir) if organized_dir else "",
        "model": (model or "qwen3:8b").strip(),
        "auto_enabled": bool(auto_enabled),
    })
    _save(data)
