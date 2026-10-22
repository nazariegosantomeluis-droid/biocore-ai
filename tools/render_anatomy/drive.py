"""Renderiza specs/*.json con three.js en Chromium headless -> out/<name>.png (+ anclas)."""
import functools
import http.server
import json
import os
import sys
import threading
import time

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
SSAA = 2


def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=HERE)
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main(names):
    srv = serve()
    port = srv.server_address[1]
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                          "--ignore-gpu-blocklist", "--enable-webgl"])
        for name in names:
            spec_path = os.path.join(HERE, "specs", name + ".json")
            spec = json.load(open(spec_path))
            w, h = spec["size"]
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=SSAA)
            page = ctx.new_page()
            logs = []
            page.on("console", lambda m: logs.append(m.text))
            page.on("pageerror", lambda e: logs.append("PAGEERROR " + str(e)))
            t0 = time.time()
            page.goto(f"http://127.0.0.1:{port}/render.html?spec=specs/{name}.json")
            try:
                page.wait_for_function("window.__done === true || window.__error !== null", timeout=600_000)
            except Exception as exc:
                print(name, "TIMEOUT", exc, logs[-5:])
                ctx.close()
                continue
            err = page.evaluate("window.__error")
            if err:
                print(name, "ERROR", err, logs[-5:])
                ctx.close()
                continue
            anchors = page.evaluate("window.__anchors")
            raw = os.path.join(HERE, "out", name + "@2x.png")
            page.locator("canvas").screenshot(path=raw, omit_background=True)
            img = Image.open(raw).convert("RGBA")
            img = img.resize((w, h), Image.LANCZOS)
            img.save(os.path.join(HERE, "out", name + ".png"))
            with open(os.path.join(HERE, "out", name + ".anchors.json"), "w") as fh:
                json.dump(anchors, fh, indent=1)
            print(f"{name}: {w}x{h} en {time.time() - t0:.1f} s, {len(anchors)} anclas", [l for l in logs if 'GPU stall' not in l][-3:])
            ctx.close()
        browser.close()
    srv.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
