"""Public, Qt-independent text selection transfer object."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionPayload:
    text: str
    pdf_page: int
    bounding_boxes: tuple
    document_id: str
    document_path: str
    requires_ocr: bool = False

    def validate(self):
        if self.pdf_page < 1:
            raise ValueError("pdf_page must be one-based")
        if not self.document_path:
            raise ValueError("document_path is required")
        for box in self.bounding_boxes:
            if len(box) != 4 or box[2] < box[0] or box[3] < box[1]:
                raise ValueError("bounding_boxes must contain normalized PDF rectangles")


def payload_from_words(words, *, pdf_page, document_id, document_path, requires_ocr=False):
    """Build a stable selection payload from PyMuPDF word tuples."""

    ordered = sorted(words, key=lambda word: (word[5], word[6], word[7]))
    lines, current_key, current = [], None, []
    for word in ordered:
        key = (word[5], word[6])
        if key != current_key and current:
            lines.append(" ".join(current))
            current = []
        current_key = key
        current.append(str(word[4]))
    if current:
        lines.append(" ".join(current))
    payload = SelectionPayload(
        text="\n".join(lines),
        pdf_page=int(pdf_page),
        bounding_boxes=tuple(tuple(float(value) for value in word[:4]) for word in ordered),
        document_id=str(document_id or ""),
        document_path=str(document_path),
        requires_ocr=bool(requires_ocr),
    )
    payload.validate()
    return payload
