# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.5 - 2026-09-03

### Improvements

- Standalone reader/editor tabs now share the title bar with the window controls, removing the duplicate title row.
- Tab labels use the compact `file.pdf [Read/GPU]` or `[Edit/CPU]` format.
- Direct2D GPU pages now keep per-primitive grayscale antialiasing explicit and show a small renderer engine badge on the page for diagnostics.
- GPU scene preparation now has a one-second page budget; pages that exceed it keep the CPU tile path instead of blocking the reader.
- Linear and compatible radial PDF shadings now use Direct2D gradient primitives instead of many small vector bands.

### Fixes

- CPU/GPU labels now follow actual page rasterization. CPU tiles composed by the GPU show CPU; partly CPU-rasterized pages show CPU+GPU.
