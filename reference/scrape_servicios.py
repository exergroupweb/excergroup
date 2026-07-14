"""
Scrape puntual de la pagina /nuestros-servicios del sitio Canva original.
Reusa la logica de scrape_exer.py pero apuntado a una sola URL.
"""
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://exergroup.my.canva.site/nuestros-servicios"
OUT_DIR = Path(__file__).parent
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def rgb_to_hex(rgb_str):
    nums = re.findall(r'[\d.]+', rgb_str)
    if len(nums) >= 3:
        r, g, b = int(float(nums[0])), int(float(nums[1])), int(float(nums[2]))
        return f"#{r:02x}{g:02x}{b:02x}"
    return rgb_str


def main():
    images_dir = OUT_DIR / "images"
    screenshots_dir = OUT_DIR / "screenshots"
    images_dir.mkdir(exist_ok=True)
    screenshots_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1000)

        scroller_handle = page.evaluate_handle("""() => {
            const all = document.querySelectorAll('*');
            let best = null, bestScroll = 0;
            for (const el of all) {
                if (el.scrollHeight > el.clientHeight + 50 && el.clientHeight > 200) {
                    if (el.scrollHeight > bestScroll) { best = el; bestScroll = el.scrollHeight; }
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
                scroller.evaluate("(el, y) => el.scrollTo(0, y)", y)
                page.wait_for_timeout(300)
                total_height = scroller.evaluate("el => el.scrollHeight")
                y += client_height
            scroller.evaluate("el => el.scrollTo(0, 0)")
            page.wait_for_timeout(800)
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

        shot_path = screenshots_dir / "servicios.png"
        page.screenshot(path=str(shot_path), full_page=True)
        print(f"[OK] Screenshot: {shot_path.name}")

        if scroller:
            page.evaluate("""() => {
                if (window._origStyles) {
                    for (const [node, style] of window._origStyles) { node.setAttribute('style', style); }
                }
            }""")

        texts = page.eval_on_selector_all(
            "body *",
            """els => els
                .filter(e => e.children.length === 0 && e.innerText && e.innerText.trim().length > 1)
                .map(e => e.innerText.trim())
            """
        )
        texts = list(dict.fromkeys(texts))

        img_urls = set(page.eval_on_selector_all("img", "els => els.map(e => e.src).filter(Boolean)"))
        bg_urls = page.eval_on_selector_all(
            "body *",
            "els => els.map(e => getComputedStyle(e).backgroundImage).filter(v => v && v.includes('url('))"
        )
        for bg in bg_urls:
            m = re.findall(r'url\(["\']?([^"\')]+)["\']?\)', bg)
            img_urls.update(m)

        downloaded_imgs = []
        for i, img_url in enumerate(list(img_urls)[:40]):
            try:
                full_url = urllib.parse.urljoin(URL, img_url)
                ext = full_url.split('?')[0].split('.')[-1][:4] or 'png'
                if len(ext) > 4 or not ext.isalnum():
                    ext = 'png'
                fname = f"servicios_img_{i:02d}.{ext}"
                fpath = images_dir / fname
                req = urllib.request.Request(full_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    fpath.write_bytes(resp.read())
                downloaded_imgs.append(fname)
            except Exception as e:
                print(f"[SKIP] {img_url[:60]} ({e})")

        browser.close()

    result = {"slug": "servicios", "url": URL, "texts": texts, "images": downloaded_imgs}
    out_json = OUT_DIR / "relevamiento_servicios.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[OK] Guardado en {out_json}")
    print(f"\n=== TEXTOS ({len(texts)}) ===")
    for t in texts:
        print(f" - {t}")
    print(f"\n=== IMAGENES ({len(downloaded_imgs)}) ===")
    for i in downloaded_imgs:
        print(f" - {i}")


if __name__ == "__main__":
    main()
