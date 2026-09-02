# sPDF 1.27.0 Release Notes

Release date: 2026-09-02

## 1.27.0 - 2026-09-02

### Performance improvements

- PDFs containing stroked text, stroke-and-clip text, or stroked vector clipping can stay on the Direct2D path more often instead of switching the whole page to CPU rendering.
