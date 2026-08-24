# sPDF

English | [한국어](README.ko.md)

A lightweight Windows desktop PDF editor built with PyQt5 and PyMuPDF. See
[PLAN.md](PLAN.md) for design history and [LICENSES.md](LICENSES.md) for
open-source notices.

## Features

- Read encrypted and regular PDFs with lazy page and thumbnail rendering.
- Open PDF-compatible Adobe Illustrator (`.ai`) files without overwriting the
  Illustrator source when saving edits.
- Select, search, copy, annotate, edit, rotate, remove, merge, split, extract,
  organize, and print pages.
- Reduce PDF size with lossless, balanced, or strong image compression.
- Cycle the left panel between hidden, page thumbnails, and PDF bookmarks;
  follow document links with Ctrl+click.
- Run offline Korean and English OCR with RapidOCR, with optional
  PaddleOCR-VL high-quality OCR.
- Work with multiple documents in tabs, move unsaved tabs between windows,
  use two-page view, full screen, and presentation mode.
- Use English or Korean UI and receive update notes in the selected language.

## Installation

Download the Windows installer from the
[latest GitHub release](https://github.com/loselessss/sPDF/releases/latest).
The application automatically checks at most once every 24 hours, or you can
use **Help → Check for Updates** at any time. Automatic updates only accept an
installer whose version matches the release and whose SHA-256 digest is
verified.

To run from source:

```bash
pip install PyQt5 PyMuPDF
pip install rapidocr onnxruntime
python run.py
python run.py document.pdf
```

Use `run.pyw` to start without a console window.

## Windows integration

The installer can add sPDF to the per-user **Open with** list for PDF and
PDF-compatible Illustrator files. It does not silently force sPDF as the
default application. **Help → Default PDF App /
Browser Settings** shows the current association and provides per-user options
for Edge, Chrome, and Firefox to hand PDF links to the Windows default PDF app.

For a development checkout without installation:

```bash
python register_filetype.py
python register_filetype.py --unregister
```

## Build

```bat
build_exe.bat
build_installer.bat
```

`build_exe.bat` creates the application and OCR worker with PyInstaller.
`build_installer.bat` packages them with Inno Setup. A pushed `vX.Y.Z` tag runs
the release workflow and publishes the versioned installer, latest alias, and
SHA-256 file.

The version in `pdfeditor/meta.py` and `installer.iss` must always match.

## Release status

- [x] **v0.1–v0.3 Viewer foundation** — document opening, lazy thumbnails,
  zoom and navigation, text selection/search/copy, annotations, saving, recent
  files, and favorites.
- [x] **v0.4–v0.9 OCR and editing** — offline RapidOCR, OCR preprocessing,
  text editing, undo/redo, page operations, and scanned-document editing.
- [x] **v1.0–v1.3 Distribution and document workflow** — Windows installer,
  optional PaddleOCR-VL, tabbed documents, merge, split, and extraction.
- [x] **v1.4–v1.6 Window and page organization** — move saved or unsaved tabs
  between windows, browser PDF settings, hand/text tools, favorites command,
  page organizer, and resizable long-document thumbnails.
- [x] **v1.7–v1.9 Navigation and Fluent UI** — HiDPI rendering, accurate text
  selection, clearer Windows process identity, antialiasing, Fluent-style UI,
  thumbnail viewport navigation, and fit/zoom commands.
- [x] **v1.10 Printing** — Ctrl+P with all/current/range/reverse printing.
- [x] **v1.11 Presentation and two-page view** — paired page navigation,
  full-screen and presentation modes, rotation commands, and update-free
  embedded-module operation.
- [x] **v1.12 International edition** — English UI and help content with a
  translation catalog independent of PDF and OCR languages.
- [x] **v1.12.1 Localized documentation and updates** — English default
  README/changelog, separate Korean documents, English/Korean UI selection,
  and updater notes matched to the selected UI language.
- [x] **v1.13.0 Illustrator support** — open, drag, organize, and merge
  PDF-compatible `.ai` files; register sPDF in the Windows **Open with** list;
  export edits to PDF so the Illustrator source remains untouched.
- [x] **v1.14.0 PDF optimization and navigation** — lossless/balanced/strong
  size reduction, hidden/thumbnail/bookmark sidebar modes, and safe Ctrl+click
  navigation for document and web links.
- [ ] **Planned: AI OCR option** — Claude API for difficult content such as
  handwriting.

## Source layout

```text
pdfeditor/
  core.py             PDF access, save, render, text, annotations
  viewer.py           thumbnails, main view, zoom, navigation
  textsel.py          selection, copy, search
  annots.py           highlights, notes, save, change tracking
  editing.py          text editing and undo/redo
  pages.py            page rotation, deletion, merge, split, extraction
  help.py             localized user guide
  startpage.py        home, favorites, recent files
  ocr.py              GUI-side OCR coordination
  ocr_subprocess.py   isolated OCR worker protocol
  vl.py               optional PaddleOCR-VL setup
  settings.py         per-user settings
  app.py              main window composition
  meta.py             application version
```
