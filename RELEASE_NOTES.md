# sPDF 1.18.0 Release Notes

Release date: 2026-08-31

## 1.18.0 Highlights

- Standalone sPDF opens in a reader. Use the edit icon or Ctrl+E to open the document in a separate editor at the same page and zoom.
- Saving updates matching reader windows in the same sPDF session without moving their view. Save As preserves the original reader's file.
- An already-open editor is reused with its unsaved edits intact. Reader and editor windows can be closed independently.
- Text editing includes font-size and color controls and a dedicated toolbar button. Existing page tools, annotations, and manual OCR remain available in the editor.
- Reader zoom updates immediately around the pointer, then sharpens the visible area. Small rendering tiles and a bounded cache avoid full-page high-resolution images at 800% zoom or in two-page view.
- Reader windows use OpenGL image composition when available and fall back to CPU display otherwise. Hidden and closed tabs cancel pending rendering work.
- Failed file replacement keeps your edits available for retry. Failed text edits restore the previous content.
- Fixed a menu-bar lifetime issue when switching or closing tabs.
- Embedded applications keep their existing editing, annotation, and self-update policies.

OpenGL accelerates image composition, not PDF interpretation or rasterization: those still use PyMuPDF on the CPU. Editor and embedded display paths are unchanged.
