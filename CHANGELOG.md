# Changelog

## Unreleased

- CSV files are now decoded once: byte-order marks, Windows-1252 (Excel) and UTF-16 files are handled, and an Encoding option was added to Reading options.
- Empty columns are dropped on load and reported, duplicated column names are reported, and read errors are shown as short readable messages.
- The C parser engine is used for all reads (about 3 times faster on large files); a comma is assumed when no separator can be detected.
- Removed the leftover code of the abandoned component-based zoom synchronisation. X-axis zoom is still synchronised within a dashboard, natively by Plotly through shared x-axes.
- Dashboard date filtering no longer keeps a copy of the filtered dataframe in session state.
- Numeric conversion no longer fails silently: text values that cannot be read as numbers are ignored and reported (with a hint for decimal commas), text series are flagged, and aggregation no longer falls back to raw data or crashes on text columns.
- Plots only copy the columns they use instead of the whole dataset.

## 0.2.0 - 2026-07-01

- Added recent CSV history with quick access in the main loader and compare tab.
- Improved CSV loading feedback, read report placement, and explicit error signaling.
- Added CSV reload support for faster fix-and-refresh workflows.
- Improved dashboard creation flow with clearer naming and dashboard-first wording.
- Added dashboard plot editing with live preview in `Dashboards Manager`.
- Added dashboard plot removal in `Dashboards Manager`.
- Added dashboard x-axis synchronization by in-chart zoom interaction.
- Removed the shared x-axis slider in favor of direct zoom-driven synchronization.
- Improved dashboard rendering reliability so saved plot types and styles are preserved.
