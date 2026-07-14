from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = Path(__file__).parent
OUT = BASE / "qa_screenshots"
OUT.mkdir(exist_ok=True)

PAGES = ["index.html", "nosotros.html", "contacto.html"]
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 834, "height": 1112},
    "mobile": {"width": 390, "height": 844},
}

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    errors = []
    for vp_name, vp in VIEWPORTS.items():
        context = browser.new_context(viewport=vp)
        page = context.new_page()
        page.on("console", lambda msg: errors.append(str(msg)) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        for pg in PAGES:
            url = (BASE / pg).as_uri()
            page.goto(url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(500)
            page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
            total_height = page.evaluate("document.body.scrollHeight")
            y = 0
            while y < total_height:
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(150)
                total_height = page.evaluate("document.body.scrollHeight")
                y += vp["height"]
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(600)
            shot = OUT / f"{pg.replace('.html','')}_{vp_name}.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"[OK] {shot.name}")
        context.close()
    browser.close()

    print("\n=== CONSOLE/PAGE ERRORS ===")
    if errors:
        for e in errors:
            print(" -", e)
    else:
        print(" (ninguno)")
