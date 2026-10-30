import os, pathlib
from playwright.sync_api import sync_playwright

VIDEO_DIR = r"c:\Users\HP LAPTOP\Documents\NVIDIA\video"
STILLS_DIR = os.path.join(VIDEO_DIR, "stills")
os.makedirs(STILLS_DIR, exist_ok=True)

HTML_URI = pathlib.Path(os.path.join(VIDEO_DIR, "film.html")).as_uri()

TIMES = [
    ("01_act1_100_figures_intro", 1.8),
    ("02_act1_70_figures_fail", 8.2),
    ("03_act2_fork_api_bug", 15.6),
    ("04_act2_math_web_pollution", 20.6),
    ("05_act3_mjolnir_tavily_3stage", 33.8),
    ("06_act3_super_ultra_escalation", 38.4),
    ("07_act4_3d_landing_cursor", 43.2),
    ("08_act4_workbench_split_assay", 49.6),
    ("09_act5_100_standing_emerald", 57.4),
    ("10_act5_mjolnir_end_lockup", 64.5),
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(HTML_URI)
        page.wait_for_function("window.__READY === true", timeout=20000)

        for name, t in TIMES:
            page.evaluate(f"window.seek({t}, 3)")
            out = os.path.join(STILLS_DIR, f"{name}.jpg")
            page.screenshot(path=out, type="jpeg", quality=92)
            print(f"[STILL] {name} @ {t}s -> {out}")

        browser.close()

if __name__ == "__main__":
    main()
