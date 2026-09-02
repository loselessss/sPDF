# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.27.0 - 2026-09-02

### Performance improvements

- Stroked PDF text can now use exact glyph outlines on the Direct2D path.
- Stroke-and-clip text and stroked vector clipping are converted to GPU clipping geometry instead of forcing a whole-page CPU fallback.

### Improvements

- Non-uniformly transformed stroked text, special blend modes, non-isolated translucent groups, and uncommon unsupported effects continue to use the complete PyMuPDF path to preserve display quality.
