"""사용자 설정 — ~/.spdf.json (최근 파일/즐겨찾기 등)."""

import json
import os

PATH = os.path.expanduser("~/.spdf.json")
_OLD_PATH = os.path.expanduser("~/.pdfeditor.json")  # 개명 전 설정 파일
MAX_RECENT = 10


def _load():
    # sPDF로 개명하면서 설정 파일도 이사 — 예전 파일이 있으면 한 번만 옮긴다.
    if not os.path.exists(PATH) and os.path.exists(_OLD_PATH):
        try:
            os.rename(_OLD_PATH, PATH)
        except OSError:
            pass
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # 파일이 없거나 깨졌으면 새로 시작 — 설정 파일 때문에 앱이 못 뜨면 안 된다.
        return {}


def _save(data):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def recent_files():
    return list(_load().get("recent", []))


def push_recent(path):
    path = os.path.abspath(path)
    d = _load()
    rest = [p for p in d.get("recent", [])
            if os.path.normcase(p) != os.path.normcase(path)]
    d["recent"] = [path] + rest[:MAX_RECENT - 1]
    _save(d)


def remove_recent(path):
    d = _load()
    d["recent"] = [p for p in d.get("recent", [])
                   if os.path.normcase(p) != os.path.normcase(path)]
    _save(d)


def clear_recent():
    d = _load()
    d["recent"] = []
    _save(d)


# --- 즐겨찾기 ----------------------------------------------------------

def favorites():
    return list(_load().get("favorites", []))


def is_favorite(path):
    path = os.path.normcase(os.path.abspath(path))
    return any(os.path.normcase(p) == path for p in favorites())


def add_favorite(path):
    path = os.path.abspath(path)
    d = _load()
    favs = [p for p in d.get("favorites", [])
            if os.path.normcase(p) != os.path.normcase(path)]
    d["favorites"] = favs + [path]
    _save(d)


def remove_favorite(path):
    d = _load()
    d["favorites"] = [p for p in d.get("favorites", [])
                      if os.path.normcase(p) != os.path.normcase(path)]
    _save(d)


# --- OCR 엔진 선택 ------------------------------------------------------
# "rapidocr": 기본(가벼운 CPU, 한글+영문). "vl": PaddleOCR-VL(고품질 AI,
# 모델 수 GB·GPU 권장). vl은 모델이 실제로 설치돼 있을 때만 유효하다.

OCR_ENGINES = ("rapidocr", "vl")


def ocr_engine():
    e = _load().get("ocr_engine", "rapidocr")
    return e if e in OCR_ENGINES else "rapidocr"


def set_ocr_engine(engine):
    if engine not in OCR_ENGINES:
        return
    d = _load()
    d["ocr_engine"] = engine
    _save(d)
