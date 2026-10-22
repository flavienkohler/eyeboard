# Changelog

## 0.3.0 (unreleased)

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
- The application state is now typed (`AppState`): every key the app owns is declared once with its type and default, and a mistyped key is an error instead of a silent new entry.
- EyeBoard is now an installable package with a command: `uv run eyeboard` (extra options go to Streamlit). The `app/` folder, the `sys.path` tricks and the PowerShell launcher are gone; `run_app.bat` is a short wrapper that checks for `uv`. Supported Python is 3.11 to 3.13, and the minimum versions of the dependencies (Streamlit 1.49, pandas 2.2.2, plotly 5.18, pydantic 2.7) are tested.
- All files now live in one data folder (`%APPDATA%/eyeboard` on Windows, or `EYEBOARD_HOME`) instead of the working directory. Dashboards are saved as `dashboards.json`; files from earlier versions are copied there on first start (originals untouched). The sidebar shows where recent files are kept and can clear them. A recent-files index can no longer point outside its folder.
- Every plot is now built by one code path (with or without a secondary axis or a "color by" column), which removes visible inconsistencies: areas are overlapping and filled and bars are grouped everywhere, "color by" now works together with a secondary axis (and keeps several Y series apart, which it did not before), styles apply the same way on both axes, the legend is horizontal, and axis titles default to the series name. Traces with more than 5,000 points use WebGL for smooth zooming.
- The interface is reorganised in four tabs: Explore, Plot, Dashboards and Compare. The sidebar is for data only (upload, recent files, reading options, and a card describing the loaded file).
- Explore shows one table with the type, missing share, exact distinct count, range and checks of every column, and a search box that also filters the column plots. The read report lists what was detected on its own, marked `(auto)`, including the date order that was used (`day first`, `month first`, `year first`, or ambiguous), and a banner warns about numbers written with a decimal comma.
- The Plot tab puts the controls beside the figure. Series colors are saved only when "Customize series" is on, so default colors no longer end up in saved dashboards. The same form is used to edit a saved plot.
- Dashboards and their management are one tab: plots can be moved up and down, removing a plot or deleting a dashboard asks for confirmation, names must be unique (an imported duplicate is numbered), and an import is recognized by its content.
- Compare takes the loaded file as A and a second file as B, draws every plot of the chosen dashboards as an overlay or side by side, and gives RMSE, MAE, bias and correlation per series, lined up by timestamps or by elapsed time.
- Added synthetic demo data (a "Try the demo data" button, and the files in `examples/`).
- Charts can be exported as standalone HTML, plotted data and comparison metrics as CSV, and as PNG through the chart toolbar.
- The interface can be switched to French (selector at the bottom of the sidebar). Texts go through a small translation table with English as the fallback, and tests check that the French table is complete.
- Added a logo, an About box in the sidebar (version, author links, link to the issue forms), and issue forms for bug reports and ideas. The displayed version now comes from the installed package.
- A new plot starts from the first real measurement instead of the first numeric column, which could be a row counter or a constant.
- The page header is one line instead of four large metrics; the read report is no longer truncated; the title of a chart no longer collides with its legend.
- The app now listens on this machine only (`--server.address 0.0.0.0` to change it).
- Added a GitHub Actions workflow that runs ruff and the tests on Python 3.11 to 3.13.

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
