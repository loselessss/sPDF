# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.4 - 2026-09-05

### Performance improvements

- Image masks and geometry clips now limit temporary Direct2D composition surfaces to their visible bounds, reducing repeated full-window GPU copies on complex pages.
