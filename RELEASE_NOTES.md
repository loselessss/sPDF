# sPDF 1.21.0 Release Notes

Release date: 2026-09-01

## 1.21.0 - 2026-09-01

### New features

- The installer now adds separate **sPDF Reader** and **sPDF Editor** shortcuts to the Start menu. Each shortcut opens its named workspace directly, regardless of the saved startup preference.
- Reader and Editor desktop shortcuts can be selected independently during installation.

### Improvements

- Updating from an earlier version removes the old single sPDF shortcut while keeping one application, installer, and update path.
- Fixed an issue where the reader could open but fail to connect to a new editor window in some Windows environments.
- Editors now open directly on the detailed canvas, while Page Organization opens in a separate thumbnail-grid window. The redundant mode header and editor marker in the window title were removed; the tab marker remains.
- The detail view now shows the current page's original size in millimetres on the bottom status bar.
- Removed the persistent editing hint from the bottom bar. Dropped PDF and AI files now open in new tabs from any area of the main window.
