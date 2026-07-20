import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import fitz
except ImportError:  # 코어 이동/메타데이터 테스트는 PyMuPDF 없이도 실행한다.
    fitz = None
    sys.modules["fitz"] = types.SimpleNamespace()

from paperorganizer import core as paperlib


class PaperLibraryTests(unittest.TestCase):
    def _make_pdf(self, path):
        if fitz is None:
            Path(path).write_bytes(b"placeholder pdf")
            return
        doc = fitz.open()
        page = doc.new_page()
        text = (
            "A Reliable Method for Scientific Document Classification\n"
            "Abstract\nThis paper presents a reliable local method for classifying "
            "academic documents. The method is evaluated on several datasets. " * 12
        )
        page.insert_textbox(fitz.Rect(40, 40, 550, 780), text, fontsize=10)
        doc.save(path)
        doc.close()

    def test_process_paper_moves_pdf_and_writes_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            input_dir = Path(temp) / "input"
            output_dir = Path(temp) / "organized"
            input_dir.mkdir()
            source = input_dir / "paper.pdf"
            self._make_pdf(str(source))
            answer = {
                "title": "A Reliable Method",
                "authors": ["A. Researcher"],
                "year": 2026,
                "category": "Computer Science",
                "subcategory": "Document AI",
                "keywords": ["classification"],
                "summary_ko": "논문 분류 방법을 제안한다.",
                "contributions": ["로컬 분류 방법"],
                "limitations": ["제한된 데이터셋"],
                "confidence": 0.91,
            }
            with mock.patch.object(paperlib, "extract_paper_text",
                                   return_value="English paper text " * 100), \
                    mock.patch.object(
                        paperlib, "_ollama_request", return_value=answer):
                record, destination = paperlib.process_paper(
                    str(source), str(output_dir), "qwen3:8b")

            destination = Path(destination)
            self.assertFalse(source.exists())
            self.assertFalse((input_dir / "paper.pdf.spdf.lock").exists())
            self.assertTrue(destination.exists())
            sidecar = destination.with_suffix(".pdf" + paperlib.META_SUFFIX)
            self.assertTrue(sidecar.exists())
            saved = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(saved["category"], "Computer Science")
            self.assertEqual(record["pdf_path"],
                             "Computer Science/Document AI/paper.pdf")
            loaded = paperlib.load_library(str(output_dir))
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["title"], "A Reliable Method")

    def test_discover_only_stable_top_level_pdfs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_pdf = root / "old.pdf"
            old_pdf.write_bytes(b"pdf")
            os.utime(old_pdf, (1, 1))
            nested = root / "nested"
            nested.mkdir()
            (nested / "ignored.pdf").write_bytes(b"pdf")
            self.assertEqual(
                paperlib.discover_input_pdfs(str(root)), [str(old_pdf)])

    def test_failure_keeps_source_and_removes_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "paper.pdf"
            source.write_bytes(b"pdf")
            with mock.patch.object(
                    paperlib, "extract_paper_text",
                    side_effect=paperlib.PaperError("OCR 필요")):
                with self.assertRaises(paperlib.PaperError):
                    paperlib.process_paper(
                        str(source), str(Path(temp) / "organized"), "qwen3:8b")
            self.assertTrue(source.exists())
            self.assertFalse(Path(str(source) + ".spdf.lock").exists())

    def test_existing_lock_prevents_duplicate_processing(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "paper.pdf"
            source.write_bytes(b"pdf")
            Path(str(source) + ".spdf.lock").write_text("other", encoding="ascii")
            with self.assertRaises(paperlib.PaperBusy):
                paperlib.process_paper(
                    str(source), str(Path(temp) / "organized"), "qwen3:8b")

    def test_safe_folder_removes_windows_invalid_characters(self):
        self.assertEqual(paperlib._safe_folder("AI/ML:*?", "Review"), "AI ML")

    def test_normalize_result_handles_loose_model_values(self):
        result = paperlib._normalize_result({
            "authors": "A. Researcher", "keywords": None,
            "year": "2025", "confidence": "1.4",
        })
        self.assertEqual(result["authors"], ["A. Researcher"])
        self.assertEqual(result["year"], 2025)
        self.assertEqual(result["confidence"], 1.0)


if __name__ == "__main__":
    unittest.main()
