# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.24.0 - 2026-09-02

### Performance improvements

- Pages using nested vector clipping can remain on the direct GPU path, improving redraw responsiveness for more ordinary PDFs.
- Colored stencil images such as simple one-color logos and icons can remain on the GPU path with their original color and transparency.

### Improvements

- Clipped text, shapes, and placed images preserve their original clipping boundaries while zooming, rotating, and panning.
- Text clipping, soft/clip masks, shading, transparency groups, and complex stroke styles continue to use the complete PyMuPDF path to preserve display quality.

## 1.23.0 - 2026-09-02

### New features

- Standalone reader and editor windows now upload visible 512-pixel PDF tiles to a Direct2D bitmap cache on supported Windows systems.
- A new display-renderer menu lets standalone users choose Auto, GPU (Direct2D), or CPU (PyMuPDF); changes take effect after restarting sPDF.
- Document window titles show the active `[GPU]` or `[CPU]` display device, and the GPU choice is disabled when Direct2D hardware rendering is unavailable.

### Performance improvements

- Direct3D 11, a DXGI flip-model swap chain, and Direct2D now composite page previews, detailed tiles, search highlights, text selections, and editable-text outlines on the GPU.
- Common pages containing text, shapes, and placed images can now be drawn directly through the GPU path for faster redraws while zooming and panning.
- Existing PDF text keeps its original shape and placement. Pages that exceed the bounded image cache automatically use the complete CPU fallback.
- Hidden and closed tabs release their native bitmaps and surfaces, while the existing 64 MiB per-tab tile limit continues to bound detailed image caches.

### Improvements

- Native initialization, presentation, or device failures fall back to the existing Qt display path without closing the document or changing interaction coordinates.
- Scrolling beyond the top or bottom edge in Edit mode no longer changes pages automatically.

### Other

- Pages using complex clipping, shading, masks, transparency groups, or stroke styles keep the complete PyMuPDF path to preserve display quality.

## 1.22.0 - 2026-09-01

### New features

- The standalone editor now uses the same OpenGL image-composition and visible-region tile display as the reader.

### Performance improvements

- Zooming and panning in the editor reuse the existing preview immediately, then sharpen only visible 512-pixel tiles. Detailed image caching remains bounded to 64 MiB per tab.
- Systems without usable OpenGL continue through the CPU display path with the same editing coordinates and saved output.

### Improvements

- After a document is handed to Edit mode successfully, sPDF closes its reader tab and closes the reader process when it was the last tab. Failed or timed-out opens leave the reader unchanged.
- Switching from an editor to a reader now checks unsaved work, hands off the document, and closes the source editor tab so the same file does not keep overlapping workspace modes.
