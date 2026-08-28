# sPDF

English | [한국어](README.ko.md)

sPDF is a Windows desktop PDF reader and editor for everyday document work.
It combines fast reading, practical page editing, annotations, offline OCR, and
multi-document tools in one lightweight application. Documents stay on your
computer unless you explicitly use an external link or optional model download.

**Current version: 1.16.7** · English and Korean interface · Windows

## What sPDF is for

### Read and navigate comfortably

- Open regular and encrypted PDFs with nearby-page rendering that stays usable
  on long documents.
- Switch the left panel between page thumbnails, PDF bookmarks, and a hidden
  view.
- Click a precise point in a sidebar thumbnail to center that part of a zoomed
  page. Page reordering is kept in the dedicated page organizer.
- Use two-page view, full screen, or presentation mode, and return to earlier
  page/zoom/scroll positions with Alt+Left and Alt+Right.
- Reopen a document where you stopped reading and Ctrl+click document or web
  links.

### Edit and organize documents

- Select, search, and copy text; add highlights and notes.
- Correct text in ordinary or OCR-processed PDFs with undo and redo.
- Rotate, delete, reorder, insert, merge, split, and extract pages.
- Add, rename, delete, reorder, and nest PDF bookmarks.
- Import a bookmark outline from a plain-text file, including nested entries.
- Crop visible page margins by dragging a preview, for one page, a range, or the
  whole document.
- Add text watermarks to selected pages and convert images to PDF or PDF pages
  to PNG/JPEG.
- Use one print window for preview, printer selection, portrait/landscape/auto
  orientation, copies, all/current/range pages, reverse order, and one-sided or
  two-sided output.
- Reduce file size with lossless, balanced, or strong compression presets.

### Work with scanned documents

- Run Korean and English OCR locally with RapidOCR; no network connection is
  required for the default engine.
- Add a searchable, selectable text layer to scanned PDFs and edit recognized
  text using its page coordinates.
- Optionally install PaddleOCR-VL for difficult pages that benefit from a
  heavier OCR model.

### Keep a practical desktop workflow

- Open multiple documents in tabs and drag saved or unsaved tabs between sPDF
  windows.
- Use favorites and recent files, thumbnail position markers, fit-page and
  fit-width controls, and hand/text-selection tools.
- Recover unsaved edits after an interrupted standalone session from a separate
  copy, without automatically overwriting the original.
- Open PDF-compatible Adobe Illustrator (`.ai`) files and export edits as PDF so
  the Illustrator source is preserved.
- Use the interface, help, installer, update notice, and release notes in English
  or Korean.

## Get sPDF

Download the Windows installer from the
[latest GitHub release](https://github.com/loselessss/sPDF/releases/latest).
The installer can add sPDF to the current user's **Open with** list, but it does
not silently force sPDF as the Windows default PDF application.

In sPDF, **Help → Default PDF App / Browser Settings** shows the current Windows
association and offers per-user options for Edge, Chrome, and Firefox to pass PDF
links to the Windows default PDF application.

sPDF checks for updates at most once every 24 hours. You can also check manually
from **Help → Check for Updates**. Downloaded installers are accepted only when
their release version and SHA-256 digest match.

## Useful shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+O / Ctrl+S / Ctrl+P | Open, save, or print |
| Ctrl+F | Find text |
| Ctrl+Z / Ctrl+Y | Undo or redo |
| Ctrl+B | Bookmark the current page |
| Alt+Left / Alt+Right | Previous or next view |
| Ctrl+R / Ctrl+Shift+R | OCR current page or whole document |
| F5 / F11 | Presentation or full-screen mode |

Press **F1** in the application for the complete localized guide.

## Important behavior

- Text editing replaces content within the original line or box. It is not a
  full text-reflow editor, and replacement fonts can look different.
- Margin cropping changes the visible page area; it does not erase the hidden
  content. Crop and bookmark changes support undo/redo.
- TXT bookmark import accepts `1 | Introduction`, `Introduction | 1`, or
  `1 Introduction`; indent a child entry with two spaces or one tab.
- Two-sided output still requires a duplex-capable printer and driver. Zoom
  rendering reuses page display data and reduces excess high-resolution work;
  PyMuPDF itself remains CPU-rendered rather than using a direct GPU backend.
- Recovery copies refresh every 30 seconds while edits are pending. Protected
  PDFs and copies over 512 MB are excluded, and recovered documents use
  **Save As** first. Recovery complements normal saving; it does not replace it.
- PDF-compatible `.ai` files can be read because they contain a PDF
  representation. Saving edits creates a PDF instead of overwriting the
  Illustrator source.

## For developers

sPDF is built with Python, PyQt5, and PyMuPDF. RapidOCR runs in a separate worker
process so its runtime is loaded only when OCR is requested.

```bash
pip install PyQt5 PyMuPDF rapidocr onnxruntime
python run.py
python run.py document.pdf
```

Use `run.pyw` to launch without a console. Windows packages are built with
`build_exe.bat` followed by `build_installer.bat`.

See [CHANGELOG.md](CHANGELOG.md) for release history, [PLAN.md](PLAN.md) for
design history and enduring constraints, and [LICENSES.md](LICENSES.md) for
open-source notices.
