# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.1 - 2026-09-04

### Improvements

- PDF soft-mask transfer functions now stay on the Direct2D path with a GPU alpha transfer table instead of forcing whole-page CPU fallback.
- Simple colored vector tiling patterns now expand into Direct2D scene items instead of forcing whole-page CPU fallback.
- Approximate CPU islands can absorb small overlapping drawables into the same bounded raster island, reducing duplicate vector edges while keeping forced GPU rendering active.
- Consecutive same-color text glyph outlines are compacted into combined page-space paths, reducing GPU scene items and native path resources without changing PDF model coordinates.
- Linear and radial gradient primitives now fold redundant surrounding clip wrappers into the gradient item when the geometry is identical, reducing scene commands for complex pages.
- An opt-in experimental similar-color band merge can compare aggressive GPU scene compaction separately from the default exact-color path.
- Interactive zoom now reuses the current GPU scene immediately and defers image-quality scene refresh until zoom input settles.
