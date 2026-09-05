# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.7 - 2026-09-05

### Improvements

- Rendering diagnostics now list CPU responsibilities alongside GPU scene contents, including tile rendering and scene/image preparation.

- GPU-drawn gradients are no longer reported as CPU bitmap work. Diagnostics distinguish rasterized gradients and CPU-composited transparency regions.
