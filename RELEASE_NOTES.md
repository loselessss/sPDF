# sPDF 1.26.0 Release Notes

Release date: 2026-09-02

## 1.26.0 - 2026-09-02

### New features

- Rendering diagnostics can show the active page path—direct GPU drawing, GPU composition, or CPU fallback—and explain why a fallback occurred.

### Performance improvements

- PDFs containing soft masks, image clip masks, dashed lines, or custom line caps and joins can stay on the Direct2D path more often instead of switching the whole page to CPU rendering.
