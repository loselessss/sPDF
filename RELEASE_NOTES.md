# sPDF 1.22.0 Release Notes

Release date: 2026-09-01

## 1.22.0 - 2026-09-01

### New features

- The standalone editor now uses the same OpenGL image-composition and visible-region tile display as the reader.

### Performance improvements

- Zooming and panning in the editor reuse the existing preview immediately, then sharpen only the visible regions. Detailed image caching remains bounded to 64 MiB per tab.
- Systems without usable OpenGL continue through the CPU display path without changing editing coordinates or saved output.

### Improvements

- After a document is handed to Edit mode successfully, sPDF closes its reader tab and closes the reader process when it was the last tab. Failed or timed-out opens leave the reader unchanged.
- Switching from an editor to a reader now checks unsaved work, hands off the document, and closes the source editor tab.
