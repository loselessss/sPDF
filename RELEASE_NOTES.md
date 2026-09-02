# sPDF 1.28.3 Release Notes

Release date: 2026-09-02

## 1.28.0 highlights - 2026-09-02

### Performance improvements

- Isolated PDF groups using Soft Light, Multiply, Screen, Overlay, and seven other blend modes can now stay on the GPU path with their original backdrop and group opacity.

## 1.28.1 improvements - 2026-09-02

- Hue, Saturation, Color, and Luminosity blends in isolated PDF groups now also use GPU effects, preserving the backdrop and group opacity.

## 1.28.2 improvements - 2026-09-02

- Blended PDF groups inside nested geometry and text clips now also stay on the GPU path, preserving the backdrop and clipped edges.

## 1.28.3 improvements - 2026-09-02

- Blends and clipping inside alpha, luminosity, and image masks now also use the GPU, including nested masks.
- Colored luminosity masks follow PDF soft-mask color conversion, and grayscale mask images preserve their image interpolation settings.
- Non-isolated/knockout groups and mask transfer functions continue to use the CPU fallback.
