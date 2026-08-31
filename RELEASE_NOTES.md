# sPDF 1.20.0 Release Notes

Release date: 2026-08-31

## 1.20.0 - 2026-08-31

### New features

- Reader and editor workspaces now run in separate OS processes. Editor shutdowns, crashes, and hangs leave the reader available; opening Edit mode can launch a fresh editor.
- Added Reader first (default) and Editor first startup settings, plus Open reader in the editor's File menu.

### Improvements

- Workspaces use independent document copies. Completed saves refresh connected readers without moving the page, zoom, or scroll position; failed or timed-out refreshes preserve the last good copy.
- Saves validate a temporary PDF before atomic replacement and preserve a backup. Conflicting editors cannot silently overwrite newer saves; failed saves retain pending edits.
- Unsaved editor recovery continues independently when the reader exits. Embedded reader, annotation, and self-update policies remain unchanged.
