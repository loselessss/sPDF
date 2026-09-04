# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.29.3 - 2026-09-04

### Performance improvements

- Direct2D pages are retained behind ABI v18 and replayed through one native call per frame. Compatible scenes are also cached as native Direct2D command lists.
