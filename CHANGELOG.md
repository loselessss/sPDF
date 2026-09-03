# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.0 - 2026-09-03

### New Features

- Editor mode now has current-page canvas size controls.
- Editor mode can set TrimBox/BleedBox page bleed margins without scaling existing artwork.
- Editable text elements can be resized from the editor context menu.
- The Direct2D renderer can keep self-contained unsupported transparency groups on the GPU path by rasterizing only that bounded group region as a CPU island, with a small approximate island path for difficult local knockout effects.
