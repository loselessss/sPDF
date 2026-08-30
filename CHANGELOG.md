# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.17.2 - 2026-08-30

### Improvements

- Embedded hosts can independently choose read-only viewing, annotation editing and annotation autosave.
- Notes and highlights can be saved separately and restored without modifying the original PDF, or exported in an annotated PDF.
- Unsaved annotation failures and concurrent saves no longer risk silently replacing another window's annotations.

### Fixes

- Deferred UI translation until widget construction finishes to prevent crashes when opening additional windows.
