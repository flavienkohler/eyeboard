# EyeBoard

Streamlit app to:

- load CSV data with flexible parsing
- build plots and save them into reusable dashboards
- re-render saved dashboards on new datasets
- compare the same dashboards across two CSV files

## Quick Start

You need [uv](https://docs.astral.sh/uv/) (a fast Python package manager). From the project folder:

```bash
uv run eyeboard
```

This installs the dependencies on first use and opens EyeBoard in your browser. Extra options go to Streamlit, for example `uv run eyeboard --server.port 8600`.

On Windows you can also double-click `run_app.bat`: it checks that `uv` is installed (and offers to install it), then runs the same command.

Supported: Python 3.11 to 3.13.

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

## Where files are kept

EyeBoard stores its files in one data folder, whatever the directory it is started from:

- `dashboards.json`: your saved dashboards (a versioned format; older files are migrated automatically and a backup copy is kept).
- `recent/`: copies of the CSV files you opened, for the "Recent CSVs" list. The sidebar shows the exact location and has a "Clear recent files" button.

The folder is `%APPDATA%/eyeboard` on Windows (the standard per-user data folder on other systems). Set the `EYEBOARD_HOME` environment variable to use another folder.

Files kept by earlier versions in the working directory (`saved_configs.json`, `data/.recent_csvs`) are copied to the data folder the first time the app starts; the originals are left in place.

## Development

```bash
uv sync                  # install the app and the dev tools
uv run pytest            # run the tests
uv run ruff check .      # lint
uv run ruff format .     # format
uv run pre-commit install
```

## Notes

- `uv.lock` pins the exact versions used in development; the declared minimum versions are tested.
- Streamlit app settings are in `.streamlit/config.toml`.

## License

EyeBoard is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). You are free to use, study and modify it for any noncommercial purpose, provided the copyright notice and license terms stay with it. Commercial use requires the author's permission.

If you use or present this work, please cite it (see [CITATION.cff](CITATION.cff); GitHub shows a "Cite this repository" button).

## AI assistance

Developed with the assistance of Claude (Anthropic) for code review and refactoring.
