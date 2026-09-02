# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.26.0 - 2026-09-02

### New features

- Optional rendering diagnostics show whether the current page uses direct GPU drawing, GPU composition, or the CPU fallback, together with the fallback reason.

### Performance improvements

- PDFs using alpha or luminosity soft masks and image clip masks can remain on the Direct2D path instead of switching the whole page to CPU rendering.
- Dashed lines, line caps, joins, and custom miter limits are now rasterized through Direct2D.

### Improvements

- Special blend modes, non-isolated translucent groups, stroked clipping paths, and uncommon unsupported effects continue to use the complete PyMuPDF path to preserve display quality.
