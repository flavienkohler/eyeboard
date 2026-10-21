# Changelog

## Unreleased

- CSV files are now decoded once: byte-order marks, Windows-1252 (Excel) and UTF-16 files are handled, and an Encoding option was added to Reading options.
- Empty columns are dropped on load and reported, duplicated column names are reported, and read errors are shown as short readable messages.
- The C parser engine is used for all reads (about 3 times faster on large files); a comma is assumed when no separator can be detected.
- Removed the leftover code of the abandoned component-based zoom synchronisation. X-axis zoom is still synchronised within a dashboard, natively by Plotly through shared x-axes.
- Dashboard date filtering no longer keeps a copy of the filtered dataframe in session state.
- Numeric conversion no longer fails silently: text values that cannot be read as numbers are ignored and reported (with a hint for decimal commas), text series are flagged, and aggregation no longer falls back to raw data or crashes on text columns.
- Plots only copy the columns they use instead of the whole dataset.
- Error handling is narrower and logged: unexpected failures are no longer swallowed, a corrupt recent-files index is moved aside instead of overwritten, and invalid series colors are reported in the log.
- `saved_configs.json` and the recent-files index are written atomically, so a crash can no longer leave a half-written file.
- Timestamps are stored in UTC (`...Z`) and shown in local time.
- Unified the vocabulary: what used to be called template, config or saved config is now always a "dashboard", and the Plotly look is called a "theme" in the code.
- Added typed dashboard models (pydantic) and a versioned file format with automatic migration from the original list format. Not yet used by the interface.

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
