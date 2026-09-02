# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.1 - 2026-09-02

### Performance improvements

- Isolated PDF groups using Hue, Saturation, Color, or Luminosity can now stay on the GPU rendering path, preserving the backdrop and group opacity.
- Unsupported nested clip/mask combinations and non-isolated/knockout groups continue to use the CPU fallback.
