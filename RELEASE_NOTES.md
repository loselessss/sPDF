# sPDF 1.23.0 Release Notes

Release date: 2026-09-02

## 1.23.0 - 2026-09-02

### New features

- Reader and editor windows now use Direct2D to display visible PDF regions on supported Windows systems.
- Choose Auto, GPU (Direct2D), or CPU (PyMuPDF) from the display-renderer menu. Restart sPDF after changing it.
- Document window titles show the active `[GPU]` or `[CPU]` device. The GPU choice is disabled when Direct2D hardware rendering is unavailable.

### Performance improvements

- Page previews, detailed visible regions, search results, text selections, and editable-text outlines are composited by the GPU.
- Common pages containing text, shapes, and placed images can now use the direct GPU path for faster redraws while zooming and panning, without changing the original text shape or placement.
- GPU resources are released when a tab is hidden or closed, and detailed image caching remains bounded to 64 MiB per tab.

### Improvements

- If the GPU display cannot start or stops working, sPDF keeps the document open and switches to its existing display path.
- Pages using complex clipping, shading, masks, transparency groups, or stroke styles automatically keep the complete PyMuPDF display path to preserve quality.
- Scrolling past a page edge in Edit mode no longer moves automatically to the previous or next page.
