"""
Exer Group - Web Scraper con Playwright (usando Edge del sistema, sin descargar Chromium)
Extrae textos, colores, tipografias, imagenes, estructura y screenshots.
"""

import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "https://exergroup.my.canva.site"
OUT_DIR = Path(__file__).parent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

START_PATHS = ["/"]


def rgb_to_hex(rgb_str):
    nums = re.findall(r'[\d.]+', rgb_str)
    if len(nums) >= 3:
        r, g, b = int(float(nums[0])), int(float(nums[1])), int(float(nums[2]))
        return f"#{r:02x}{g:02x}{b:02x}"
    return rgb_str


def extract_page_data(page, slug, url, images_dir, screenshots_dir):
    print(f"\n=== {slug.upper()} - {url} ===")

    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1000)

    # Canva sites render inside an internal scrollable div, not <body>.
    # Find the largest scrollable container on the page.
    scroller_handle = page.evaluate_handle("""() => {
        const all = document.querySelectorAll('*');
        let best = null, bestScroll = 0;
        for (const el of all) {
            if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 200) {
                if (el.scrollHeight > bestScroll) {
                    best = el;
                    bestScroll = el.scrollHeight;
                }
            }
        }
        return best;
    }""")
    scroller = scroller_handle.as_element()

    if scroller:
        total_height = scroller.evaluate("el => el.scrollHeight")
        client_height = scroller.evaluate("el => el.clientHeight")
        y = 0
        while y < total_height:
            scroller.evaluate(f"(el, y) => el.scrollTo(0, y)", y)
            page.wait_for_timeout(300)
            total_height = scroller.evaluate("el => el.scrollHeight")
            y += client_height
        scroller.evaluate("el => el.scrollTo(0, 0)")
        page.wait_for_timeout(800)

        # Temporarily expand the scrollable container (and all its ancestors)
        # so the full_page screenshot captures everything instead of just the viewport
        scroller.evaluate("""el => {
            window._origStyles = [];
            let node = el;
            while (node && node !== document.documentElement.parentElement) {
                window._origStyles.push([node, node.getAttribute('style') || '']);
                node.style.height = 'auto';
                node.style.maxHeight = 'none';
                node.style.minHeight = '0';
                node.style.overflow = 'visible';
                if (node === document.body || node === document.documentElement) break;
                node = node.parentElement;
            }
        }""")
        page.wait_for_timeout(300)
    else:
        page.wait_for_timeout(500)

    # Screenshot full content
    shot_path = screenshots_dir / f"{slug}.png"
    page.screenshot(path=str(shot_path), full_page=True)
    print(f"  [OK] Screenshot: {shot_path.name}")

    if scroller:
        page.evaluate("""() => {
            if (window._origStyles) {
                for (const [node, style] of window._origStyles) {
                    node.setAttribute('style', style);
                }
            }
        }""")

    # Texts (visible only)
    texts = page.eval_on_selector_all(
        "body *",
        """els => els
            .filter(e => e.children.length === 0 && e.innerText && e.innerText.trim().length > 1)
            .map(e => e.innerText.trim())
        """
    )
    texts = list(dict.fromkeys(texts))

    # Colors + fonts from computed styles
    style_data = page.eval_on_selector_all(
        "body *",
        """els => els.map(e => {
            const s = getComputedStyle(e);
            return {
                color: s.color,
                bg: s.backgroundColor,
                font: s.fontFamily,
                size: s.fontSize,
                weight: s.fontWeight
            };
        })"""
    )
    colors = set()
    fonts = set()
    for sd in style_data:
        if sd['color'] and sd['color'] not in ('rgba(0, 0, 0, 0)',):
            colors.add(rgb_to_hex(sd['color']))
        if sd['bg'] and sd['bg'] not in ('rgba(0, 0, 0, 0)',):
            colors.add(rgb_to_hex(sd['bg']))
        if sd['font']:
            fonts.add(sd['font'])

    # Image URLs (img + background-image)
    img_urls = set(page.eval_on_selector_all(
        "img", "els => els.map(e => e.src).filter(Boolean)"
    ))
    bg_urls = page.eval_on_selector_all(
        "body *",
        """els => els.map(e => getComputedStyle(e).backgroundImage)
            .filter(v => v && v.includes('url('))
        """
    )
    for bg in bg_urls:
        m = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', bg)
        img_urls.update(m)

    # Nav links
    nav_links = page.eval_on_selector_all(
        "a[href]",
        """els => els.map(e => ({text: e.innerText.trim(), href: e.href}))
            .filter(l => l.text)
        """
    )

    # Download images
    downloaded_imgs = []
    for i, img_url in enumerate(list(img_urls)[:40]):
        try:
            full_url = urllib.parse.urljoin(url, img_url)
            ext = full_url.split('?')[0].split('.')[-1][:4] or 'png'
            if len(ext) > 4 or not ext.isalnum():
                ext = 'png'
            fname = f"{slug}_img_{i:02d}.{ext}"
            fpath = images_dir / fname
            req = urllib.request.Request(full_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10) as resp:
                fpath.write_bytes(resp.read())
            downloaded_imgs.append(fname)
        except Exception as e:
            print(f"  [SKIP] {img_url[:60]} ({e})")

    print(f"  Textos: {len(texts)} | Colores: {len(colors)} | Fuentes: {len(fonts)} | Imagenes: {len(downloaded_imgs)}/{len(img_urls)} | Links: {len(nav_links)}")

    return {
        "slug": slug,
        "url": url,
        "texts": texts,
        "colors": sorted(colors),
        "fonts": sorted(fonts),
        "nav_links": nav_links,
        "images": downloaded_imgs,
    }


def main():
    images_dir = OUT_DIR / "images"
    screenshots_dir = OUT_DIR / "screenshots"
    images_dir.mkdir(exist_ok=True)
    screenshots_dir.mkdir(exist_ok=True)

    results = {}
    visited = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # First pass: home page, discover nav links
        home_url = BASE_URL + "/"
        data = extract_page_data(page, "home", home_url, images_dir, screenshots_dir)
        results["home"] = data
        visited.add(home_url.rstrip('/'))

        # Discover internal pages from nav links
        to_visit = []
        for link in data.get("nav_links", []):
            href = link["href"]
            if href.startswith(BASE_URL) and href.rstrip('/') not in visited:
                to_visit.append(href)
        to_visit = list(dict.fromkeys(to_visit))

        for href in to_visit:
            slug = href.replace(BASE_URL, "").strip("/").replace("/", "_") or "home"
            if href.rstrip('/') in visited:
                continue
            visited.add(href.rstrip('/'))
            try:
                data = extract_page_data(page, slug, href, images_dir, screenshots_dir)
                results[slug] = data
            except Exception as e:
                print(f"  ERROR en {href}: {e}")
                results[slug] = {"error": str(e)}

        browser.close()

    out_json = OUT_DIR / "relevamiento.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Relevamiento guardado: {out_json}")
    print(f"[OK] Imagenes en: {images_dir}")
    print(f"[OK] Screenshots en: {screenshots_dir}")

    print("\n=== RESUMEN DE TEXTOS POR PAGINA ===")
    for slug, data in results.items():
        if "error" in data:
            print(f"\n[{slug}] ERROR: {data['error']}")
            continue
        print(f"\n[{slug}]")
        for t in data.get("texts", [])[:10]:
            print(f"  - {t}")
        if len(data.get("texts", [])) > 10:
            print(f"  ... (+{len(data['texts']) - 10} mas)")

    print("\n=== PALETA DE COLORES ===")
    all_colors = set()
    for data in results.values():
        if "colors" in data:
            all_colors.update(data["colors"])
    for c in sorted(all_colors)[:30]:
        print(f"  {c}")

    print("\n=== TIPOGRAFIAS ===")
    all_fonts = set()
    for data in results.values():
        if "fonts" in data:
            all_fonts.update(data["fonts"])
    for f in sorted(all_fonts):
        print(f"  {f}")


if __name__ == "__main__":
    main()
