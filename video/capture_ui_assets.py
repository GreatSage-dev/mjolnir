import json, os, time
from playwright.sync_api import sync_playwright

OUT_DIR = r"c:\Users\HP LAPTOP\Documents\NVIDIA\video\assets\ui"
os.makedirs(OUT_DIR, exist_ok=True)

def main():
    coords = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()

        # 1. Capture Landing Page Hero + Scroll Section
        page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        page.wait_for_timeout(600)
        cta = page.locator("a.button, a[href*='/app']").first
        if cta.count() > 0:
            coords["landing_cta"] = cta.bounding_box()
        page.screenshot(path=os.path.join(OUT_DIR, "landing_hero.png"))

        # Also capture full-page height slice for 56-deg 3D flyover!
        page.screenshot(path=os.path.join(OUT_DIR, "landing_full.png"), full_page=True)

        # 2. Capture Workbench (/app)
        page.goto("http://127.0.0.1:8080/app", wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(OUT_DIR, "app_default.png"))

        # Inspect interactive elements on /app
        info = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button, select, [data-task-id], [data-nav-view]')).map(el => ({
                tag: el.tagName,
                id: el.id,
                cls: el.className,
                text: (el.innerText || '').trim().slice(0, 60),
                nav: el.getAttribute('data-nav-view'),
                taskId: el.getAttribute('data-task-id'),
                rect: el.getBoundingClientRect().toJSON()
            }));
            return btns;
        }""")
        with open(os.path.join(OUT_DIR, "app_elements.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        # Select api-06 task if select or task list exists
        sel = page.locator("select").first
        if sel.count() > 0:
            coords["task_select"] = sel.bounding_box()
            options = sel.locator("option").all_inner_texts()
            print("Select options:", options[:6])
            # Pick api-06 if available
            val = page.evaluate("""() => {
                const s = document.querySelector('select');
                if (!s) return null;
                for (const o of s.options) {
                    if (o.value.includes('api-06') || o.text.includes('api-06') || o.value.includes('api-01')) {
                        s.value = o.value;
                        s.dispatchEvent(new Event('change', {bubbles: true}));
                        return o.value;
                    }
                }
                return s.value;
            }""")
            print("Selected task:", val)
            page.wait_for_timeout(400)

        # Find Run / Execute button
        run_btn = page.locator("button:has-text('Run'), button:has-text('Execute'), button:has-text('Assay'), #run-assay-btn, #runBtn").first
        if run_btn.count() > 0:
            coords["run_btn"] = run_btn.bounding_box()
            page.screenshot(path=os.path.join(OUT_DIR, "app_selected.png"))
            run_btn.click()
            page.wait_for_timeout(2500)
            page.screenshot(path=os.path.join(OUT_DIR, "app_verified_result.png"))

            # Scroll down inside main content if diff receipt is below fold
            page.evaluate("""() => {
                const scrollers = [document.scrollingElement, ...document.querySelectorAll('main, .main, .workspace, .content, .sheet')];
                for (const el of scrollers) {
                    if (el && el.scrollHeight > el.clientHeight + 60) {
                        el.scrollTop = Math.min(420, el.scrollHeight - el.clientHeight);
                    }
                }
                window.scrollTo(0, 360);
            }""")
            page.wait_for_timeout(400)
            page.screenshot(path=os.path.join(OUT_DIR, "app_diff_scrolled.png"))

        # Switch to 5-Arm Ledger view if nav exists
        ledger_nav = page.locator("[data-nav-view*='ledger'], [data-nav-view*='benchmark'], button:has-text('Ledger'), button:has-text('5-Arm'), a:has-text('Ledger')").first
        if ledger_nav.count() > 0:
            page.evaluate("window.scrollTo(0, 0)")
            coords["ledger_nav"] = ledger_nav.bounding_box()
            ledger_nav.click()
            page.wait_for_timeout(600)
            page.screenshot(path=os.path.join(OUT_DIR, "app_ledger.png"))

        with open(os.path.join(OUT_DIR, "ui_coords.json"), "w", encoding="utf-8") as f:
            json.dump(coords, f, indent=2)

        browser.close()
        print("Captured UI assets successfully. Coords keys:", list(coords.keys()))

if __name__ == "__main__":
    main()
