# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.22.0 - 2026-09-01

### New features

- The standalone editor now uses the same OpenGL image-composition and visible-region tile display as the reader.

### Performance improvements

- Zooming and panning in the editor reuse the existing preview immediately, then sharpen only visible 512-pixel tiles. Detailed image caching remains bounded to 64 MiB per tab.
- Systems without usable OpenGL continue through the CPU display path with the same editing coordinates and saved output.

### Improvements

- After a document is handed to Edit mode successfully, sPDF closes its reader tab and closes the reader process when it was the last tab. Failed or timed-out opens leave the reader unchanged.
- Switching from an editor to a reader now checks unsaved work, hands off the document, and closes the source editor tab so the same file does not keep overlapping workspace modes.
