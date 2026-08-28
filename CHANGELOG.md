# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.16.7 - 2026-08-28

### Improvements

- Restyle the integrated print window with Fluent cards, spacing, typography, preview framing, and an accent Print button consistent with the rest of sPDF.

## 1.16.6 - 2026-08-27

### Improvements

- Add Auto, Portrait, and Landscape paper orientation to the integrated print window. Auto follows each selected PDF page's orientation in preview and output where the printer driver supports per-page changes.

## 1.16.5 - 2026-08-27

### Bug fixes

- Remove the unused outer-window status bar that left an empty strip below the document status bar. Shell messages now use the active document's existing status bar.

## 1.16.4 - 2026-08-27

### Improvements

- Combine print preview, printer selection, page range, reverse order, copy count, and one-sided/duplex choices into the Ctrl+P print window. Remove the separate preview and print-sides menu entries.

## 1.16.3 - 2026-08-27

### Improvements

- Rename the top-level `Page` menu to `Page Organization` so its document-structure tools are easier to identify.

## 1.16.2 - 2026-08-27

### Bug fixes

- Make the unsaved-changes dialog buttons follow the selected sPDF interface language instead of showing Qt's English `Save` and `Discard` labels on a Korean interface.

## 1.16.1 - 2026-08-27

### Improvements

- Make the regular sidebar thumbnails navigation-only. Clicking a point still centers that location in the zoomed document, while drag reordering is now available only in the dedicated page organizer.

## 1.16.0 - 2026-08-27

### New features

- Return to earlier views with Alt+Left / Alt+Right, including page, zoom, and scroll position. Reopening a document restores its last reading position.
- Add the current page as a bookmark with Ctrl+B, rename or delete bookmarks from the sidebar, and drag them to change order or nesting. Bookmark edits support undo/redo.
- Drag an area to keep in the page-margin crop preview and apply relative margins to the current page, a range, or all pages. Cropping changes the visible area without erasing content and supports undo/redo.
- Standalone sPDF saves separate recovery copies every 30 seconds while edits are pending. After an interrupted session, restore or discard copies without overwriting originals. Protected PDFs and copies over 512 MB are excluded.
- Import nested PDF bookmarks from a UTF-8, UTF-16, or CP949 text file using page-first or title-first lines.
- Add text watermarks to the current page, a page range, or the whole document with adjustable size, opacity, and angle.
- Convert multiple images to one PDF in the selected order, or export selected PDF pages to PNG or JPEG at a chosen resolution.
- Preview print output and choose one-sided, long-edge duplex, or short-edge duplex printing. Page range and reverse-order choices use the same renderer in preview and final output.

### Improvements

- Windows Explorer shows the registered document type simply as `PDF`; Illustrator support remains unchanged.
- Reorganized the README around what sPDF does, common workflows, installation, and important behavior instead of version-by-version development history.
- Reduced the left-panel ribbon menu to an icon with a tooltip and drop-down, freeing space for document controls.
- The updated application removes downloaded installer and interrupted-download files from its dedicated temporary update folder, retrying after setup releases the installer.
- Use the native Windows file picker instead of the classic Qt dialog.
- Reuse PyMuPDF page display data, debounce continuous zoom rendering, and adapt supersampling at high zoom levels to improve zoom responsiveness without increasing the installed GPU/runtime footprint.

### Bug fixes

- Removed the duplicate resize handle drawn by the outer window status bar.
