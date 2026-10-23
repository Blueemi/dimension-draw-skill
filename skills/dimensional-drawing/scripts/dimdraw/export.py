"""SVG -> PNG / PDF using whatever renderer the machine has.

Order: $DIMDRAW_CHROME, a Chromium-family browser in headless mode (including
Playwright's cached builds), rsvg-convert, cairosvg, inkscape. The SVG itself
is the master file and never depends on a renderer.
"""

import glob
import os
import re
import shutil
import subprocess
import tempfile


def _chrome_candidates():
    env = os.environ.get("DIMDRAW_CHROME")
    if env:
        yield env
    home = os.path.expanduser("~")
    pw = []
    for base in (os.path.join(home, "Library/Caches/ms-playwright"), os.path.join(home, ".cache/ms-playwright"),
                 os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")):
        if not base:
            continue
        pw += sorted(glob.glob(os.path.join(base, "chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell")), reverse=True)
        pw += sorted(glob.glob(os.path.join(base, "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium")), reverse=True)
        pw += sorted(glob.glob(os.path.join(base, "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing")), reverse=True)
        pw += sorted(glob.glob(os.path.join(base, "chromium-*/chrome-linux*/chrome")), reverse=True)
    yield from pw
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome",
                 "microsoft-edge", "brave-browser"):
        p = shutil.which(name)
        if p:
            yield p
    for p in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
              "/Applications/Helium.app/Contents/MacOS/Helium",
              "/Applications/Arc.app/Contents/MacOS/Arc",
              "C:/Program Files/Google/Chrome/Application/chrome.exe",
              "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"):
        if os.path.exists(p):
            yield p


def find_chrome():
    for c in _chrome_candidates():
        if c and os.path.exists(c):
            return c
    return None


def _run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _html(svg_text, css):
    return ("<!doctype html><html><head><meta charset='utf-8'><style>"
            "html,body{margin:0;padding:0;background:#fff;overflow:hidden}"
            f"svg{{display:block;{css}}}</style></head><body>{svg_text}</body></html>")


def _chrome_flags(tmp):
    return ["--headless", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", f"--user-data-dir={tmp}",
            "--virtual-time-budget=4000"]


def to_png(svg_path, png_path, w_mm, h_mm, px_per_mm=4.0):
    wpx, hpx = int(round(w_mm * px_per_mm)), int(round(h_mm * px_per_mm))
    chrome = find_chrome()
    if chrome:
        with tempfile.TemporaryDirectory() as tmp:
            with open(svg_path) as fh:
                svg = fh.read()
            page = os.path.join(tmp, "page.html")
            with open(page, "w") as fh:
                fh.write(_html(svg, f"width:{wpx}px;height:{hpx}px"))
            cmd = [chrome] + _chrome_flags(os.path.join(tmp, "profile")) + [
                f"--window-size={wpx},{hpx}", "--force-device-scale-factor=1",
                f"--screenshot={os.path.abspath(png_path)}", "file://" + page]
            if _run(cmd) and os.path.exists(png_path):
                return png_path
    if shutil.which("rsvg-convert"):
        if _run(["rsvg-convert", "-w", str(wpx), "-h", str(hpx), "-b", "white", "-o", png_path, svg_path]):
            return png_path
    try:
        import cairosvg  # type: ignore
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=wpx, output_height=hpx,
                         background_color="white")
        return png_path
    except Exception:
        pass
    if shutil.which("inkscape"):
        if _run(["inkscape", svg_path, "--export-type=png", f"--export-filename={png_path}",
                 f"--export-width={wpx}", "--export-background=white"]):
            return png_path
    print("no SVG renderer found (install Chrome/Chromium, librsvg or cairosvg); SVG written only")
    return None


def to_pdf(svg_path, pdf_path, w_mm, h_mm):
    chrome = find_chrome()
    if chrome:
        with tempfile.TemporaryDirectory() as tmp:
            with open(svg_path) as fh:
                svg = fh.read()
            page = os.path.join(tmp, "page.html")
            css = f"width:{w_mm}mm;height:{h_mm}mm"
            with open(page, "w") as fh:
                fh.write(_html(svg, css).replace(
                    "<style>", f"<style>@page{{size:{w_mm}mm {h_mm}mm;margin:0}}"))
            cmd = [chrome] + _chrome_flags(os.path.join(tmp, "profile")) + [
                "--no-pdf-header-footer", "--print-to-pdf-no-header",
                f"--print-to-pdf={os.path.abspath(pdf_path)}", "file://" + page]
            if _run(cmd) and os.path.exists(pdf_path):
                return pdf_path
    if shutil.which("rsvg-convert"):
        if _run(["rsvg-convert", "-f", "pdf", "-o", pdf_path, svg_path]):
            return pdf_path
    try:
        import cairosvg  # type: ignore
        cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
        return pdf_path
    except Exception:
        pass
    print("no PDF renderer found (install Chrome/Chromium, librsvg or cairosvg)")
    return None


def to_pdf_multi(svg_texts, pdf_path, w_mm, h_mm):
    """One PDF page per SVG sheet (needs a Chromium-family browser)."""
    chrome = find_chrome()
    if not chrome:
        print("multi-page PDF needs Chrome/Chromium; write single-sheet PDFs instead")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        body = "".join(f"<div class='pg'>{s}</div>" for s in svg_texts)
        doc = ("<!doctype html><html><head><meta charset='utf-8'><style>"
               f"@page{{size:{w_mm}mm {h_mm}mm;margin:0}}html,body{{margin:0;padding:0}}"
               f".pg{{width:{w_mm}mm;height:{h_mm}mm;page-break-after:always;overflow:hidden}}"
               f".pg:last-child{{page-break-after:auto}}svg{{display:block;width:{w_mm}mm;height:{h_mm}mm}}"
               f"</style></head><body>{body}</body></html>")
        page = os.path.join(tmp, "doc.html")
        with open(page, "w") as fh:
            fh.write(doc)
        cmd = [chrome] + _chrome_flags(os.path.join(tmp, "profile")) + [
            "--no-pdf-header-footer", "--print-to-pdf-no-header",
            f"--print-to-pdf={os.path.abspath(pdf_path)}", "file://" + page]
        if _run(cmd) and os.path.exists(pdf_path):
            return pdf_path
    return None


def crop_svg(svg_text, x0, y0, x1, y1):
    """Same drawing, viewBox narrowed to a sheet-mm region."""
    w, h = x1 - x0, y1 - y0
    head_end = svg_text.index(">") + 1
    head = svg_text[:head_end]
    head = re.sub(r'width="[^"]*"', f'width="{w}mm"', head, count=1)
    head = re.sub(r'height="[^"]*"', f'height="{h}mm"', head, count=1)
    head = re.sub(r'viewBox="[^"]*"', f'viewBox="{x0} {y0} {w} {h}"', head, count=1)
    return head + svg_text[head_end:]
