# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.5 - 2026-09-05

### Performance improvements

- Geometry clips that do not cross a mask or blend target switch now use lightweight Direct2D layers instead of temporary composition surfaces.
- Retained Direct2D scenes now reuse linear and radial gradient brushes instead of rebuilding their stops and brushes on every frame.
- Automatic and forced GPU modes use faster axis-aligned clipping for simple rectangular paths after keeping measured edge differences within 2/255 of the geometry clip output. The native renderer ABI is now v19.
- Automatic mode now detects highly complex pages with a quick full-page command probe, shows the CPU result without waiting for GPU scene extraction, and replaces it with the cached GPU scene when isolated background preparation finishes.

### Bug fixes

- Background GPU preparation now starts when a deferred document tab first becomes visible, rather than leaving pages on the initial CPU display path.
- Rendering diagnostics now state explicitly when the current page uses CPU, GPU, CPU+GPU, or CPU while a background GPU scene is being prepared.
