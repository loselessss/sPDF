# sPDF 1.28.1 Release Notes

Release date: 2026-09-02

## 1.28.0 highlights - 2026-09-02

### Performance improvements

- Isolated PDF groups using Soft Light, Multiply, Screen, Overlay, and seven other blend modes can now stay on the GPU path with their original backdrop and group opacity.

## 1.28.1 improvements - 2026-09-02

- Hue, Saturation, Color, and Luminosity blends in isolated PDF groups now also use GPU effects, preserving the backdrop and group opacity.
- Unsupported nested clip/mask combinations and non-isolated/knockout groups continue to use the CPU fallback to preserve display quality.
