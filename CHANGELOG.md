# Changelog

English | [한국어](CHANGELOG.ko.md)

## 1.12.1 - 2026-08-24

### Improvements

- The default README and changelog are now written in English, with separate Korean versions linked at the top of each document.
- English and Korean can be selected from **Help → Language**. The change takes effect after restarting sPDF.
- The updater now shows the release notes that match the selected UI language. Older releases without language sections remain readable.

## 1.12.0 - 2026-08-24

### New features

- Added the English international edition covering menus, the command bar, start page, dialogs, status messages, updater, user guide, and installer.
- Introduced a separate translation catalog so additional UI languages can be added independently of feature code.

### Improvements

- Kept UI language independent from PDF content and Korean/English OCR recognition.
- Tabs now disappear immediately when closed while OCR and render-cache cleanup continues after the next UI update.

## 1.11.0 - 2026-08-24

### New features

- Added two-page view with paired thumbnail selection and two-page navigation.
- Added F11 full screen, F5 presentation mode, and command-bar page rotation.

### Improvements

- Embedded sPDF windows no longer create or expose the standalone update service.

## 1.10.0 - 2026-08-11

### New features

- Added Ctrl+P printing for all pages, current page, ranges, and reverse order.

### Fixes and improvements

- Restored page numbers for thumbnails after page 9.
- Limited automatic update checks to once every 24 hours while preserving manual checks.
- OCR runs only when explicitly requested, and shutdown no longer waits several seconds per OCR tab.

## 1.9.0 - 2026-08-11

### New features

- Added clickable thumbnail viewport navigation and zoom in, zoom out, fit width, and fit page commands.

### Bug fixes

- Corrected vertical synchronization between the thumbnail viewport indicator and the main document view.

## 1.8.0 - 2026-08-11

### New features

- Added a Fluent-inspired Windows UI with rounded surfaces, compact typography, consistent icons, and theme fallbacks.

### Bug fixes

- Fixed the recent-file card corner artifact and page-organizer rendering after page 10.
- Removed an accidental Paper Organizer source copy from the sPDF repository.

## 1.7.3 - 2026-08-09

### Improvements

- Improved text antialiasing and fractional-scale interpolation.

## 1.7.2 - 2026-08-03

### Improvements

- Improved Windows process grouping and labels for the main app and OCR worker.

### Bug fixes

- Removed unnecessary title-bar help buttons and strengthened OCR cleanup during exit.

## 1.7.1 - 2026-08-01

### Improvements

- Improved continuous text selection and copying across wrapped lines.

## 1.7.0 - 2026-08-01

### New features

- Added HiDPI document rendering, responsive thumbnails, 1% zoom controls, visible-area indication, and **Open File Location**.

## 1.6.2 - 2026-07-29

### Improvements

- Improved document and thumbnail sharpness on scaled Windows displays.

## 1.6.1 - 2026-07-29

### Improvements

- Added a resizable, persistent thumbnail-panel width.

### Bug fixes

- Fixed missing thumbnails in longer documents.

## 1.6.0 - 2026-07-26

### New features

- Added a dedicated page organizer with previews, drag-and-drop PDF/image insertion, reordering, deletion, and undo support.

## 1.5.3 - 2026-07-23

### Improvements

- Added a command-bar favorite toggle beside the hand and text tools.

## 1.5.2 - 2026-07-22

### Bug fixes

- Fixed garbled Korean build-script output and unintended command errors.

## 1.5.1 - 2026-07-22

### Improvements

- Renamed the ambiguous default OCR option to RapidOCR.

## 1.5.0 - 2026-07-22

### New features

- Added selectable hand and text-selection tools with click-and-drag document panning.

## 1.4.2 - 2026-07-22

### Improvements

- Improved OCR for low-contrast scans, long pages, and two-column layouts.

## 1.4.1 - 2026-07-22

### Improvements

- Added per-user Edge, Chrome, and Firefox PDF handoff settings.

## 1.4.0 - 2026-07-22

### New features

- Added cross-window tab transfer while preserving unsaved state and closing an emptied source window.

## 1.3.0 - 2026-07-22

### New features

- Added reinforced PDF merge and split workflows.

## 1.2.0 - 2026-07-20

### New features

- Added multi-document tabs with independent document state and draggable tab ordering.
