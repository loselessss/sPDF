# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.28.4 - 2026-09-02

### Improvements

- Standalone reader/editor tabs now share the title bar with the window controls, removing the duplicate title row.
- Tab labels use the compact `file.pdf [Read/GPU]` or `[Edit/CPU]` format.

### Fixes

- CPU/GPU labels now follow actual page rasterization. CPU tiles composed by the GPU show CPU; partly CPU-rasterized pages show CPU+GPU.
