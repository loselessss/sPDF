# sPDF 1.28.5 Release Notes

Release date: 2026-09-03

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

## 1.28.4 improvements - 2026-09-02

- Standalone document tabs now sit in the title bar, using compact labels such as `file.pdf [Read/GPU]` and `[Edit/CPU]`.
- CPU/GPU labels follow actual rasterization instead of composition. CPU tiles show CPU, while mixed rasterization shows CPU+GPU.

## 1.28.5 improvements - 2026-09-03

- GPU-rendered pages keep grayscale antialiasing enabled more explicitly for smoother vector and text-outline edges.
- Expensive GPU scene preparation falls back after a short wait so difficult pages do not hold the reader for too long.
- Common linear and radial PDF gradients stay on the GPU path with fewer drawing operations.
