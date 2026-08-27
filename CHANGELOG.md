# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.15.0 - 2026-08-27

### New features

- Return to earlier views with Alt+Left / Alt+Right, including page, zoom, and scroll position. Reopening a document restores its last reading position.
- Add the current page as a bookmark with Ctrl+B, rename or delete bookmarks from the sidebar, and drag them to change order or nesting. Bookmark edits support undo/redo.
- Drag an area to keep in the page-margin crop preview and apply relative margins to the current page, a range, or all pages. Cropping changes the visible area without erasing content and supports undo/redo.
- Standalone sPDF saves separate recovery copies every 30 seconds while edits are pending. After an interrupted session, restore or discard copies without overwriting originals. Protected PDFs and copies over 512 MB are excluded.

### Improvements

- Windows Explorer shows the registered document type simply as `PDF`; Illustrator support remains unchanged.
- Reorganized the README around what sPDF does, common workflows, installation, and important behavior instead of version-by-version development history.
- Reduced the left-panel ribbon menu to an icon with a tooltip and drop-down, freeing space for document controls.
- The updated application removes downloaded installer and interrupted-download files from its dedicated temporary update folder, retrying after setup releases the installer.

### Bug fixes

- Removed the duplicate resize handle drawn by the outer window status bar.
