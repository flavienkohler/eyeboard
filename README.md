# EyeBoard

Streamlit app to:

- load CSV data with flexible parsing
- build plots and save them into reusable dashboards
- re-render saved dashboards on new datasets
- compare the same dashboards across two CSV files

## Quick Start (Windows)

Run:

```bat
run_app.bat
```

The launcher will:

1. Detect/install `uv` if needed.
2. Ensure Python `3.11` is available.
3. Sync dependencies (`uv sync`).
4. Start Streamlit and open a browser tab.

## Launcher Logging

- Full launcher output is shown in terminal and saved to `logs/run_app_YYYYMMDD_HHMMSS.log`.
- Only the 5 latest logs are kept (automatic rotation).
- Logs are ignored by git.

## Typical Workflow

1. Load a CSV in the sidebar (`Data` section).
2. Adjust parsing in `Reading options` (separator, decimal, header, date parsing).
3. Build a plot in `Plot Builder`.
4. Save it into a dashboard.
5. Go to `Dashboard` and select one or more saved dashboards to visualize on the current CSV.
6. Go to `Compare (2 CSVs)` to visualize the same dashboard(s) side-by-side on two datasets.

## Sidebar Controls

### Data

- Upload CSV or provide a server path.
- Select the active dashboard.

### Reading Options

Use this to control CSV parsing and date parsing globally:

- `Separator`: auto-detect, comma, semicolon, tab, pipe
- `Decimal`: dot/comma
- `Header`: first row, second row, two-row multi-header, no header
- `Date/time column (optional)`
- `Date order`: auto-detect, day-first, month-first
- `Date format override (optional)`

These settings affect:

- main CSV reading
- preview mini-plots date axis behavior
- Plot Builder date filtering defaults

## Tabs

### Preview

- Quick dataframe preview
- Column names and dtypes
- Summary statistics
- Mini-plots for all columns (3-column layout)

### Plot Builder

- Choose date range and X/Y axes
- Configure plot type, optional secondary Y axis, group/color, aggregation
- Per-series style controls (color/width/dash)
- Save the current plot into a dashboard

### Dashboard

- Select one or more saved dashboards to display on current CSV
- Optional global date parsing/filtering in this tab
- One rendered figure per selected dashboard

### Compare (2 CSVs)

- Load Dataset A and Dataset B
- Select dashboard(s) to compare
- Shared optional date parsing and shared date-range filter
- Side-by-side plot rendering (A vs B) per dashboard

### Dashboards Manager

- Rename, delete, export/import dashboard JSON
- Advanced JSON edit/validate/save

## Saved dashboards

- Dashboards are stored in `saved_configs.json` locally.
- `saved_configs.json` is ignored by git (not tracked).

## Manual Run (Any OS with uv installed)

```bash
uv python install 3.11
uv sync
uv run -- streamlit run app/app.py
```

## Notes

- Commit `uv.lock` for reproducible environments.
- Streamlit app settings are in `.streamlit/config.toml`.

## License

EyeBoard is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). You are free to use, study and modify it for any noncommercial purpose, provided the copyright notice and license terms stay with it. Commercial use requires the author's permission.

If you use or present this work, please cite it (see [CITATION.cff](CITATION.cff); GitHub shows a "Cite this repository" button).

## AI assistance

Developed with the assistance of Claude (Anthropic) for code review and refactoring.
