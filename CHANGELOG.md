# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.18.0 - 2026-08-31

### New features

- Standalone sPDF starts in a read-only reader. The edit icon or Ctrl+E opens a separate editor at the current page and zoom.
- Text editing now includes font-size and color controls, with a dedicated toolbar button.
- Reader windows use OpenGL image composition when available, with automatic CPU display fallback.

### Performance

- Zoom responds immediately using existing images, then sharpens only visible page regions. The point under the pointer stays in place during wheel zoom, up to 800%.
- Reader rendering uses small tiles with a bounded cache, including in two-page view. Hidden or closed tabs cancel pending tile work.

### Improvements

- Saving refreshes matching readers in the same sPDF session while preserving their page, zoom, and scroll position. Save As leaves the original reader on its original file.
- An already-open editor is reused without losing its unsaved changes. Embedded hosts retain their existing access and update settings.

### Fixes

- A failed file replacement keeps pending edits available for another save attempt and reopens the reader.
- Failed text edits restore the previous document content without adding an undo step.
- Switching or closing document tabs no longer deletes menu bars that are still needed.
