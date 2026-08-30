# sPDF 1.17.2 Release Notes

Release date: 2026-08-30

## Embedded reading and annotations

- Host programs can turn body editing, annotation editing and annotation autosave on or off separately.
- Read-only viewing retains zoom, navigation, search, text selection/copy, existing annotations and printing.
- With annotations enabled, notes and highlights are saved beside the PDF without changing the original. They are restored when the PDF is reopened in a reader window, even with annotation editing off.
- Disable autosave to save annotations with Ctrl+S; use Ctrl+Shift+S to export a separate annotated PDF for other viewers.
- Undo/redo, close-time saving, save-error warnings and concurrent-save checks help preserve annotations. Protected PDFs do not create unencrypted annotation sidecars.
- New windows inherit the selected mode. Standalone editing and embedded self-update behavior remain unchanged.

## Window stability

- Fixed a UI translation timing issue that could crash newly created windows.
