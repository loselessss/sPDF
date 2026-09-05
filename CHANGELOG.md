# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.6 - 2026-09-05

### Bug fixes

- Fixed zoom percentages reverting after zooming in CPU and GPU modes.
- Zoom display and input now use screen DPI instead of treating PDF points as screen pixels.
- Documents always open fitted to the window width while retaining the last page.

- Fixed Windows fractional display scaling, including 150%, for the standalone interface.
- Rendering diagnostics distinguish CPU rendering with OpenGL composition and show Direct2D initialization failures.
