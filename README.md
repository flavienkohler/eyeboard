# EyeBoard

A time-series explorer for CSV files. Load a file, check at a glance how it was read and what each column holds, build plots, save them as reusable dashboards, and replay the same dashboards on another file to compare two runs. It is domain-neutral: sensors, simulations, logs, anything with a column of timestamps.

<!-- Screenshots to add here: the Explore tab, the Plot tab, the Compare overlay. -->

## Quick start

You need [uv](https://docs.astral.sh/uv/) (a fast Python package manager). From the project folder:

```bash
uv run eyeboard
```

This installs the dependencies on first use and opens EyeBoard in your browser. Extra options go to Streamlit, for example `uv run eyeboard --server.port 8600`. On Windows you can also double-click `run_app.bat`: it checks that `uv` is installed (and offers to install it), then runs the same command.

No file at hand? Click **Try the demo data** in the sidebar. It loads a synthetic weather and river station (two months, hourly), and the Compare tab offers a second, biased "model run" of the same period. The files are also in [examples/](examples) if you prefer to upload them.

Supported: Python 3.11 to 3.13.

## What it does

The sidebar is for data only: upload a file or pick a recent one, adjust the reading options, and see a card with the file that is loaded. The work happens in four tabs.

| Tab | What it is for |
| --- | --- |
| **Explore** | How the file was read, then one row per column: type, missing share, exact number of distinct values, range, and checks (constant, empty, values that are not numbers, numbers written with a decimal comma). A search box filters the table and the small per-column plots. |
| **Plot** | Controls on the left, the figure on the right. Line, scatter, bar and area plots, a secondary Y axis, grouping by a column, aggregation, per-series colors, and a date range. Save the plot into a dashboard. |
| **Dashboards** | A dashboard is a named stack of plots that does not depend on any file, so it can be redrawn on whatever file is loaded. Show several at once with a shared x axis. Under *Manage dashboards*: rename, reorder, edit and remove plots, delete, export and import as JSON. |
| **Compare** | The loaded file is A; pick B. Every plot of the chosen dashboards is drawn as an overlay (B dashed over A) or side by side, with RMSE, MAE, bias and correlation per series. B is lined up with A by timestamps or by elapsed time since each start. |

### Trusting what was detected

Automatic detection is convenient and sometimes wrong, so EyeBoard shows what it decided. The read report at the top of Explore and the card in the sidebar list the separator, decimal, encoding, header and date order, and mark the ones it found itself with `(auto)`. A banner warns when numbers look written with a decimal comma but are read as text. Values that cannot be converted to numbers are reported, never silently dropped.

### Exports

Switch on *Prepare export files* under a chart to download it as a standalone HTML page (it opens offline, zoom included), and the plotted data or the comparison metrics as CSV. For a PNG, use the camera icon in the chart's toolbar.

## Where files are kept

EyeBoard stores its files in one data folder, whatever the directory it is started from:

- `dashboards.json`: your saved dashboards, in a versioned format. Older files are migrated automatically and a backup copy is kept.
- `recent/`: copies of the CSV files you opened, for the recent files list. The sidebar shows the exact location and has a *Clear recent files* button.

The folder is `%APPDATA%/eyeboard` on Windows (the standard per-user data folder on other systems). Set the `EYEBOARD_HOME` environment variable to use another folder. Files kept by earlier versions in the working directory (`saved_configs.json`, `data/.recent_csvs`) are copied there the first time the app starts; the originals are left in place.

EyeBoard does not send any usage statistics: Streamlit's telemetry is switched off by the launcher and in `.streamlit/config.toml`.

## How it is built

```text
src/eyeboard/
  services/     pure logic, no Streamlit: reading and decoding CSV, date parsing,
                numeric conversion, column profile, comparison metrics, the
                dashboards store, demo data
  dashboards/   typed, validated models of dashboards and plots, and the file format
  plotting/     from a plot specification and a table to a Plotly figure; overlay; export
  ui/           everything that draws: the sidebar, the four tabs, the shared plot form,
                caches. The only layer that imports Streamlit (besides the launcher)
  state.py      the application state, typed
```

A few choices worth knowing:

- **Streamlit and Plotly.** Streamlit keeps the app a single Python codebase, which is the right size for a tool used by one person on their own files. The price is that the script reruns on every interaction, so loading, parsing and profiling are cached on a cheap key (the file identity and the options), and heavy output such as exports is built only on request.
- **Logic out of the interface.** The rules that matter (what counts as a number, how B is lined up on A, where a plot is added) are plain functions with tests, not code inside widgets.
- **Dashboards are data, not files.** A plot stores column names, not values. Columns are matched by normalized name when a dashboard is replayed, and the notes say what was matched or missing.
- **Validated at the edge.** Saved dashboards, imported JSON and the JSON editor all go through the same pydantic models, with readable error messages.

## Development

```bash
uv sync                      # install the app and the dev tools
uv run pytest                # run the tests (add --cov=eyeboard for coverage)
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pre-commit install    # lint and format on every commit
```

`uv.lock` pins the exact versions used in development; the declared minimum versions (Streamlit 1.49, pandas 2.2.2, plotly 5.18, pydantic 2.7) are tested. The demo files in `examples/` are generated by a seeded script (`uv run python -m eyeboard.services.demo examples`), and a test checks that they match it.

## License

EyeBoard is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE). You are free to use, study and modify it for any noncommercial purpose, provided the copyright notice and license terms stay with it. Commercial use requires the author's permission.

If you use or present this work, please cite it (see [CITATION.cff](CITATION.cff); GitHub shows a "Cite this repository" button).

## AI assistance

Developed with the assistance of Claude (Anthropic) for code review and refactoring.
