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
- Dashboards, plots and series styles are now typed and validated everywhere (Plot Builder, Dashboards Manager, JSON editor, import, plotting). The saved file uses a versioned format; the original list format is migrated automatically and copied once to `saved_configs.json.v1.bak`. Dashboards that fail validation are reported with the exact problem and backed up instead of being silently dropped.
- Importing a dashboard that already exists (for example your own export) now creates a copy with a new id.
- Loading and date parsing are now pure functions (`services/dataset.py`) cached by Streamlit on a cheap source key and the reading options, so a rerun no longer re-reads or re-parses the file. The sidebar builds the date options after the file is loaded (no more stale column list), a recent file is touched and an upload remembered once instead of on every rerun, and the dataframe is no longer kept in session state.
- Choosing "(none)" as the date column now works; the detected date column is proposed once per loaded file.
- The Dashboard and Compare tabs no longer have their own date column, order and format controls: they use the date settings of the sidebar, so every tab parses dates the same way (parsing is cached).

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
