# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.14.1 - 2026-08-24

### Improvements

- The Windows installer now asks for English or Korean and uses that choice as sPDF's initial interface language.
- The start page presents PDF as the primary file type while PDF-compatible Illustrator files remain available through the File menu and drag and drop.
- Presentation mode now accepts the arrow keys for previous and next page navigation even when the document view has keyboard focus.
- Replaced the hard-to-discover left-panel cycle icon with a labeled ribbon drop-down for Hidden, Page Thumbnails, and Bookmarks.

### Bug fixes

- The update dialog no longer mixes an English availability heading into the Korean interface, and a launched update installer defaults to the current interface language.

## 1.14.0 - 2026-08-24

### New features

- Added **Reduce PDF Size** with lossless, balanced, and strong presets. Compressed results are written to a separate PDF so the open original remains unchanged.
- The left navigation panel now cycles through hidden, page thumbnails, and the PDF's hierarchical bookmarks. Its last mode is remembered.
- Ctrl+click follows internal PDF destinations and opens web or email links in the default app, in both text-selection and hand-tool modes.

### Improvements

- File- and program-launch links embedded in PDFs are blocked for safety.
- Password-protected PDFs are left unchanged rather than silently weakening their security settings during compression.
- Bookmarks stay synchronized with the current page and refresh after page-structure edits.
