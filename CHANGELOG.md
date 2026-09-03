# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.6 - 2026-09-03

### Improvements

- PDF text whose display-list glyph id is missing can now stay on the GPU path when the same embedded/original font maps the Unicode character back to a vector glyph outline.

### Fixes

- Removed the on-screen Direct2D ABI badge from GPU-rendered pages.
