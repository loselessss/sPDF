# sPDF 1.28.0 Release Notes

Release date: 2026-09-02

## 1.28.0 - 2026-09-02

### Performance improvements

- Isolated PDF groups using Soft Light, Multiply, Screen, Overlay, and seven other blend modes can now stay on the GPU path with their original backdrop and group opacity.
- Unsupported nested clip/mask combinations, non-isolated/knockout groups, and color-component blends continue to use the CPU fallback to preserve display quality.
