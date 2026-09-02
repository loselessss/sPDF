# sPDF 1.25.0 Release Notes

Release date: 2026-09-02

## 1.25.0 - 2026-09-02

### Performance improvements

- PDFs that clip content with exact glyph outlines can now zoom and pan through Direct2D without switching the whole page to the CPU fallback.
- Axial, radial, function-based, and mesh shadings are rendered into a bounded high-quality image and composed with the rest of the page through Direct2D.
- Isolated transparency groups using normal blending are handled with Direct2D opacity layers.

### Improvements

- Soft/clip masks, special blend modes, non-isolated translucent groups, and complex stroke styles continue to use the complete PyMuPDF path to preserve display quality.
