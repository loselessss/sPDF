# sPDF 1.19.1 Release Notes

Release date: 2026-08-31

## Included 1.18.0 Highlights

- Standalone sPDF now starts in a reader window. Open a separate editor at the same page and zoom level; existing editor tabs retain unsaved changes and are reused.
- Saving refreshes reader windows in the same sPDF session without losing their reading position. Save As leaves the original reader file unchanged.
- Text editing now offers font size and color controls and a dedicated toolbar icon. Page organization, annotations, and manual OCR are available in the editor.
- Reader zoom responds immediately around the pointer, then sharpens the visible area. Bounded tile rendering avoids full-page high-resolution images, including at 800% zoom and in two-page view. Hidden or closed tabs cancel pending rendering.
- Reader windows use OpenGL image composition when supported, with CPU display as a fallback. PDF interpretation and rasterization still run on the CPU; editor and embedded display paths remain unchanged.
- Failed file replacement preserves edits for another save attempt, and failed text edits restore the previous content. Fixed menu bars being deleted incorrectly during tab switching or closing.

## 1.19.0 Highlights

- Added a large blue **Edit mode** button at the left of the reader ribbon. Ctrl+E also opens the editor.
- New editor windows start with a thumbnail grid and the current page selected. Drag individual or selected groups of pages to reorder them, drop PDFs to insert them, or delete selected pages.
- Double-click a page or press Enter for detailed editing in the same window. Use **Page overview** or Ctrl+Shift+P to return to the grid. Both views share unsaved changes and undo/redo history.
- The grid renders only visible and nearby pages, releases distant previews, and stops pending thumbnail work when hidden or closed.
- Rotate the current reader page left/right using toolbar icons, the View menu, or Ctrl+[ / Ctrl+]. This rotates the view only and never changes the PDF file. Use the editor to save a rotated page.
- Thumbnails, selection, search, links, and zoom follow the rotated view, including in two-page mode.
- Embedded applications keep their existing editing, annotation, and self-update policies.

## 1.19.1 Improvements

- Editor document tabs and window titles now display **[Edit-only]** to distinguish them from reader windows.
- Removed presentation and full-screen controls, including F5/F11 shortcuts, from standalone editor windows. Reader and embedded windows retain their existing view modes.
