# sPDF 1.24.0 Release Notes

Release date: 2026-09-02

## 1.24.0 - 2026-09-02

### Performance improvements

- Pages using nested vector clipping can remain on the direct GPU path, improving redraw responsiveness for more ordinary PDFs.
- Colored stencil images such as simple one-color logos and icons can remain on the GPU path with their original color and transparency.

### Improvements

- Clipped text, shapes, and placed images preserve their original clipping boundaries while zooming, rotating, and panning.
- Text clipping, soft/clip masks, shading, transparency groups, and complex stroke styles continue to use the complete PyMuPDF path to preserve display quality.
