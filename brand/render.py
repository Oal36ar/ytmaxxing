"""Render the brand v2 images from their HTML sources.

usage: python3 brand/render.py            (from the repo root; needs Playwright with Chromium, and network for Google Fonts)

  brand/banner.html  -> assets/banner.png          1280x420 at 2x (2560x840)
  brand/social.html  -> assets/social-preview.png  1280x640
  brand/logo/*.svg   -> brand/logo/png/*-{512,1024}.png
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGES = [("brand/banner.html", "assets/banner.png", 1280, 420, 2),
         ("brand/social.html", "assets/social-preview.png", 1280, 640, 1)]
MARKS = ["logo-mark", "logo-mark-inverse", "logo-mark-orange"]


def browser(p):
    args = ["--allow-file-access-from-files"]
    try:
        return p.chromium.launch(args=args)
    except Exception:  # use the newest cached headless shell when Playwright expects a build that isn't downloaded
        shells = sorted((Path.home() / "Library/Caches/ms-playwright").glob("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell"))
        return p.chromium.launch(args=args, executable_path=str(shells[-1]))


def main():
    with sync_playwright() as p:
        b = browser(p)
        for src, out, w, h, scale in PAGES:
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
            pg.goto((ROOT / src).as_uri())
            pg.wait_for_function("window.READY === true", timeout=60000)
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(ROOT / out))
            pg.close()
            print(out)
        for name in MARKS:
            for size in (512, 1024):
                pg = b.new_page(viewport={"width": size, "height": size})
                svg = (ROOT / "brand/logo" / f"{name}.svg").read_text()
                pg.set_content(f'<html><body style="margin:0;overflow:hidden"><style>svg{{display:block}}</style>{svg.replace("width=\"100\" height=\"100\"", f"width=\"{size}\" height=\"{size}\"", 1)}</body></html>')
                pg.screenshot(path=str(ROOT / "brand/logo/png" / f"{name}-{size}.png"), omit_background=True)
                pg.close()
                print(f"brand/logo/png/{name}-{size}.png")
        b.close()


if __name__ == "__main__":
    main()
