# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.0 - 2026-09-02

### Performance improvements

- Isolated PDF groups can now use Soft Light, Multiply, Screen, Overlay, Darken, Lighten, Color Dodge, Color Burn, Hard Light, Difference, and Exclusion through Direct2D GPU effects.
- Supported blended scenes keep GPU drawing instead of switching the whole page to CPU rendering, while retaining group opacity and the existing backdrop.

### Improvements

- Rendering diagnostics distinguish unsupported blends inside clips/masks and color-component blend modes. Non-isolated/knockout groups and unsupported combinations retain the CPU fallback.
