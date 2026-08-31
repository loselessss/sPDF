# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.19.0 - 2026-08-31

### New features

- Added a large blue **Edit mode** button at the left of the reader ribbon. The editor opens with a grid of page previews and the current page selected.
- Drag one or several pages to change their order. Double-click a page or press Enter to edit it in the same window; **Page overview** or Ctrl+Shift+P returns to the grid without losing unsaved edits or undo/redo history.

### Performance improvements

- The editor overview renders only visible and nearby thumbnails, releases off-screen previews, and stops pending thumbnail work when hidden or closed.

### Improvements

- Reader windows now offer left/right rotation through toolbar icons, the View menu, and Ctrl+[ / Ctrl+]. Only the current page's view rotates; the PDF file is unchanged.
- Thumbnails, text selection, search highlights, links, and zoom positioning follow the rotated view, including in two-page mode. Editor rotation still supports saving and undo.
