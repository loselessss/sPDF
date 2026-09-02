# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.3 - 2026-09-02

### Performance improvements

- Blends and clipping inside alpha, luminosity, and image masks can now stay on the GPU rendering path, including nested masks.

### Fixes

- Luminosity masks now follow PDF soft-mask color conversion instead of generic display luminance, including colored masks.
- Grayscale mask images are supported, and PDF image interpolation settings are preserved when zooming.
