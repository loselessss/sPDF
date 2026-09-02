# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.2 - 2026-09-02

### Performance improvements

- Blended PDF groups inside nested geometry and text clips can now stay on the GPU rendering path, preserving the backdrop and clipped edges.
- Unsupported combinations inside soft/image masks and non-isolated/knockout groups continue to use the CPU fallback.
