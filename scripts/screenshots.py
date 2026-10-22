"""Take the README screenshots of EyeBoard, with the synthetic demo data only.

Playwright is not a dependency of the project; run the script with it on demand:

    uv run --with playwright python -m playwright install chromium   # once
    uv run --with playwright --with pillow python scripts/screenshots.py [output_folder]

Pillow is only needed for the animated tour (tour.gif); without it the pictures are
still taken.

The app is started in a temporary data folder and a temporary working directory,
so no file of the person running the script can appear in a picture.
"""

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from eyeboard.dashboards.document import serialize_document
from eyeboard.dashboards.model import Dashboard, PlotSpec

PORT = 8613
VIEWPORT = {"width": 1440, "height": 2300}
OVERVIEW_CLIP = {"x": 0, "y": 0, "width": 1440, "height": 900}
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "screenshots"


def demo_dashboard() -> Dashboard:
    """A dashboard on the demo columns, so the Dashboards and Compare tabs have content."""
    return Dashboard(
        name="River station",
        plots=[
            PlotSpec(
                title="Flow and rain",
                x_col="timestamp",
                y_cols=["flow_m3s"],
                y2_cols=["rain_mm"],
            ),
            PlotSpec(title="Temperature", x_col="timestamp", y_cols=["temperature_c"]),
        ],
    )


def wait_for_server(port: int) -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://localhost:{port}/_stcore/health", timeout=1)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError("EyeBoard did not start")


def settle(page: Page, seconds: float = 2.5) -> None:
    """Wait for the page to finish its rerun and for charts to be drawn."""
    page.wait_for_timeout(int(seconds * 1000))
    page.wait_for_selector(
        '[data-testid="stStatusWidget"]', state="detached", timeout=30_000
    )
    # Elements of the previous run stay on screen, faded, until the new run replaces them.
    page.wait_for_function(
        "document.querySelectorAll('[data-stale=\"true\"]').length === 0",
        timeout=30_000,
    )


def open_tab(page: Page, name: str, seconds: float = 3.5) -> None:
    page.get_by_role("tab", name=name).click()
    settle(page, seconds)


def shoot_panel(page: Page, path: Path) -> None:
    """Picture of the open tab only (without the page header above it)."""
    page.locator('[role="tabpanel"]:visible').first.screenshot(path=str(path))


TOUR_VIEWPORT = {"width": 1280, "height": 740}
TOUR_WIDTH = 960  # pixels of the GIF; the file stays small enough for a README
# (picture name, seconds it stays on screen)
TOUR_HOLD = {
    "start": 1.6,
    "explore": 2.4,
    "search": 2.4,
    "plot": 2.6,
    "dashboards": 3.0,
    "compare": 3.6,
}


def scroll_to_chart(page: Page) -> None:
    page.locator(
        '[role="tabpanel"]:visible .stPlotlyChart'
    ).first.scroll_into_view_if_needed()
    page.wait_for_timeout(1500)  # let the tab switch finish before the picture


def record_tour(page: Page, output: Path) -> None:
    """Walk through the app on the demo data and save the steps as an animated GIF."""
    import io

    from PIL import Image

    frames: list[tuple[Image.Image, float]] = []

    def capture(name: str) -> None:
        picture = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        height = round(picture.height * TOUR_WIDTH / picture.width)
        picture = picture.resize((TOUR_WIDTH, height), Image.LANCZOS)
        frames.append((picture, TOUR_HOLD[name]))

    page.goto(f"http://localhost:{PORT}")
    settle(page, 1.5)
    capture("start")
    page.get_by_role("button", name="Try the demo data").click()
    settle(page)
    open_tab(page, "Explore", 2.0)
    capture("explore")
    search = page.get_by_placeholder("Type part of a column name")
    search.fill("flow")
    search.press("Enter")
    settle(page, 1.5)
    capture("search")
    search.fill("")
    search.press("Enter")
    open_tab(page, "Plot")
    capture("plot")
    open_tab(page, "Dashboards")
    scroll_to_chart(page)
    capture("dashboards")
    open_tab(page, "Compare", 2.5)
    page.get_by_role("combobox", name="File for B").click()
    page.get_by_text("Demo: station B (model run)").click()
    settle(page, 4)
    scroll_to_chart(page)
    capture("compare")

    palette_frames = [
        picture.quantize(
            colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
        )
        for picture, _ in frames
    ]
    palette_frames[0].save(
        output / "tour.gif",
        save_all=True,
        append_images=palette_frames[1:],
        duration=[round(seconds * 1000) for _, seconds in frames],
        loop=0,
        optimize=True,
    )


def take_screenshots(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp()) / "eyeboard_home"
    home.mkdir(parents=True)
    (home / "dashboards.json").write_text(
        serialize_document([demo_dashboard()]), encoding="utf-8"
    )

    server = subprocess.Popen(
        [
            "eyeboard",
            "--server.port",
            str(PORT),
            "--server.headless",
            "true",
            "--client.toolbarMode",
            "minimal",
        ],
        env=dict(os.environ, EYEBOARD_HOME=str(home)),
        cwd=tempfile.mkdtemp(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_server(PORT)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT)
            page.goto(f"http://localhost:{PORT}")
            page.get_by_role("button", name="Try the demo data").click()
            settle(page)

            open_tab(page, "Explore", 2.5)
            page.screenshot(path=str(output / "overview.png"), clip=OVERVIEW_CLIP)
            shoot_panel(page, output / "explore.png")

            open_tab(page, "Plot")
            shoot_panel(page, output / "plot.png")

            open_tab(page, "Dashboards")
            shoot_panel(page, output / "dashboards.png")

            open_tab(page, "Compare", 2.5)
            page.get_by_role("combobox", name="File for B").click()
            page.get_by_text("Demo: station B (model run)").click()
            settle(page, 4)
            shoot_panel(page, output / "compare.png")

            try:
                import PIL  # noqa: F401
            except ImportError:
                print("Pillow is not installed: tour.gif was not made.")
            else:
                # A fresh page, so the tour starts from the empty state.
                tour = browser.new_page(viewport=TOUR_VIEWPORT)
                record_tour(tour, output)
            browser.close()
    finally:
        server.terminate()


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUTPUT
    take_screenshots(folder)
    for picture in sorted(folder.glob("*.png")):
        print(picture)
