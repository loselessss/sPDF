# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.17.0 - 2026-08-28

### New features

- Return to earlier views with Alt+Left / Alt+Right, restore the last reading position, and recover unsaved standalone work after an interrupted session.
- Add, rename, delete, reorder, nest, and import PDF bookmarks from UTF-8, UTF-16, or CP949 text files. Bookmark edits support undo/redo.
- Crop visible page margins by dragging a preview area and add adjustable text watermarks to selected pages. Both participate in undo/redo.
- Convert multiple images into one PDF or export selected PDF pages to PNG or JPEG at a chosen resolution.
- Use one integrated print window for preview, printer selection, page range, reverse order, copies, Auto/Portrait/Landscape orientation, and one-sided or duplex output.
- Drag the blue viewport marker in a sidebar thumbnail to continuously pan around a zoomed page.

### Improvements

- Use native Windows file dialogs and show the registered document type simply as `PDF` while retaining Illustrator-compatible file support.
- Make sidebar thumbnails navigation-only: click a precise point to center a zoomed page, and use the dedicated page organizer for reordering.
- Rename the top-level Page menu to Page Organization, reduce the left-panel ribbon command to an icon, and restyle the print window with Fluent cards.
- Remove downloaded installer and interrupted-download files after an update.
- Reorganize the README around current features, workflows, installation, and important behavior.

### Performance improvements

- Reuse bounded PyMuPDF page display data, debounce continuous zoom rendering, and adapt supersampling at high zoom levels.

### Bug fixes

- Show Save, Don't Save, and Cancel in the selected interface language in the unsaved-changes dialog.
- Remove the duplicate resize handle and the unused outer status bar that left an empty strip below the document status bar.
