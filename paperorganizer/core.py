"""로컬 Ollama를 이용한 논문 분류·요약 코어."""

import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import fitz


META_SUFFIX = ".spdf.json"
MAX_SOURCE_CHARS = 30000


class PaperError(RuntimeError):
    pass


class PaperBusy(PaperError):
    pass


def _clean_text(text):
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_paper_text(path):
    """제목/초록/서론과 결론 쪽을 우선해 로컬 모델 입력을 만든다."""
    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PaperError("PDF를 열 수 없습니다: %s" % exc) from exc
    try:
        if doc.needs_pass:
            raise PaperError("암호화된 PDF는 자동 분석할 수 없습니다.")
        pages = []
        for index in range(min(doc.page_count, 8)):
            pages.append("[PAGE %d]\n%s" % (
                index + 1, doc[index].get_text("text")))
        for index in range(max(8, doc.page_count - 3), doc.page_count):
            pages.append("[PAGE %d]\n%s" % (
                index + 1, doc[index].get_text("text")))
    finally:
        doc.close()
    text = _clean_text("\n\n".join(pages))
    if len(text) < 500:
        raise PaperError("추출된 텍스트가 너무 적습니다. 먼저 OCR이 필요합니다.")
    if len(text) > MAX_SOURCE_CHARS:
        front = int(MAX_SOURCE_CHARS * 0.72)
        back = MAX_SOURCE_CHARS - front
        text = text[:front] + "\n\n[...중간 본문 생략...]\n\n" + text[-back:]
    return text


def _ollama_request(model, source_text, timeout=600):
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "authors": {"type": "array", "items": {"type": "string"}},
            "year": {"type": ["integer", "null"]},
            "category": {"type": "string"},
            "subcategory": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "summary_ko": {"type": "string"},
            "contributions": {"type": "array", "items": {"type": "string"}},
            "limitations": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        },
        "required": ["title", "authors", "year", "category", "subcategory",
                     "keywords", "summary_ko", "contributions", "limitations",
                     "confidence"],
    }
    system = (
        "You analyze English academic papers. Return only the requested JSON. "
        "Classify the paper into a stable, broad English category and an optional "
        "English subcategory. Write the summary, contributions, and limitations in "
        "Korean. Use only facts supported by the supplied text. If information is "
        "missing, use an empty value rather than guessing. Confidence must be 0..1."
    )
    prompt = (
        "Analyze this paper excerpt. Keep the Korean summary concise (3-5 sentences). "
        "Use short category folder names without slashes.\n\n" + source_text)
    payload = json.dumps({
        "model": model, "stream": False, "format": schema,
        "options": {"temperature": 0.1},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat", data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise PaperError(
            "Ollama에 연결할 수 없습니다. Ollama가 실행 중인지 확인하세요: %s" % exc
        ) from exc
    except Exception as exc:
        raise PaperError("로컬 모델 호출에 실패했습니다: %s" % exc) from exc
    try:
        return json.loads(body["message"]["content"])
    except Exception as exc:
        raise PaperError("모델 응답을 JSON으로 해석할 수 없습니다.") from exc


def _safe_folder(value, fallback):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return value[:80] or fallback


def _string_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value:
        return [str(value).strip()]
    return []


def _normalize_result(result):
    if not isinstance(result, dict):
        raise PaperError("모델 응답이 올바른 객체 형식이 아닙니다.")
    normalized = dict(result)
    for key in ("authors", "keywords", "contributions", "limitations"):
        normalized[key] = _string_list(normalized.get(key))
    for key in ("title", "category", "subcategory", "summary_ko"):
        normalized[key] = str(normalized.get(key) or "").strip()
    try:
        year = int(normalized.get("year") or 0)
        normalized["year"] = year if 1000 <= year <= 9999 else None
    except (TypeError, ValueError):
        normalized["year"] = None
    try:
        confidence = float(normalized.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    normalized["confidence"] = max(0.0, min(1.0, confidence))
    return normalized


def _unique_destination(folder, filename):
    target = folder / filename
    if not target.exists():
        return target
    stem, suffix = Path(filename).stem, Path(filename).suffix
    for number in range(2, 10000):
        candidate = folder / ("%s (%d)%s" % (stem, number, suffix))
        if not candidate.exists():
            return candidate
    raise PaperError("같은 이름의 파일이 너무 많습니다: %s" % filename)


def process_paper(pdf_path, organized_dir, model):
    """논문 하나를 분석하고 sidecar JSON과 함께 organized로 이동한다."""
    pdf_path = Path(pdf_path)
    organized_dir = Path(organized_dir)
    if not pdf_path.is_file():
        raise PaperError("입력 PDF가 없습니다.")
    lock_path = pdf_path.with_suffix(pdf_path.suffix + ".spdf.lock")
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        try:
            stale = datetime.now().timestamp() - lock_path.stat().st_mtime > 3600
            if stale:
                lock_path.unlink()
                lock_fd = os.open(
                    str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                raise PaperBusy(
                    "다른 sPDF 인스턴스가 이 논문을 처리 중입니다.") from exc
        except PaperBusy:
            raise
        except OSError as retry_exc:
            raise PaperBusy(
                "다른 sPDF 인스턴스가 이 논문을 처리 중입니다.") from retry_exc
    try:
        with os.fdopen(lock_fd, "w", encoding="ascii") as stream:
            stream.write(str(os.getpid()))
        source = extract_paper_text(str(pdf_path))
        result = _normalize_result(_ollama_request(model, source))
        category = _safe_folder(result.get("category"), "Review")
        subcategory = _safe_folder(result.get("subcategory"), "")
        destination_dir = organized_dir / category
        if subcategory:
            destination_dir = destination_dir / subcategory
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = _unique_destination(destination_dir, pdf_path.name)
        result.update({
            "schema_version": 1,
            "source_name": pdf_path.name,
            "pdf_path": str(destination.relative_to(organized_dir)).replace("\\", "/"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "model": model,
        })
        meta_target = destination.with_suffix(destination.suffix + META_SUFFIX)
        fd, temp_name = tempfile.mkstemp(
            prefix=".spdf-meta-", suffix=".tmp", dir=str(destination_dir))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            shutil.move(str(pdf_path), str(destination))
            try:
                os.replace(temp_name, str(meta_target))
            except Exception:
                if destination.exists() and not pdf_path.exists():
                    shutil.move(str(destination), str(pdf_path))
                raise
        except Exception:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise
        return result, str(destination)
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def discover_input_pdfs(input_dir, minimum_age_seconds=15):
    root = Path(input_dir)
    if not root.is_dir():
        return []
    now = datetime.now().timestamp()
    found = []
    for path in root.glob("*.pdf"):
        try:
            if now - path.stat().st_mtime >= minimum_age_seconds:
                found.append(str(path))
        except OSError:
            continue
    return sorted(found, key=lambda p: os.path.getmtime(p))


def load_library(organized_dir):
    root = Path(organized_dir)
    if not root.is_dir():
        return []
    records = []
    for path in root.rglob("*" + META_SUFFIX):
        try:
            with path.open(encoding="utf-8") as stream:
                item = json.load(stream)
            pdf = root / item.get("pdf_path", "")
            if not pdf.is_file():
                name = path.name[:-len(META_SUFFIX)]
                pdf = path.with_name(name)
            item["_meta_file"] = str(path)
            item["_pdf_file"] = str(pdf)
            records.append(item)
        except Exception:
            continue
    return sorted(records, key=lambda x: x.get("processed_at", ""), reverse=True)
