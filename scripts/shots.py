"""Screenshot viewer pages for run reports: headless Edge driven over the DevTools protocol.

    python scripts/shots.py before 1280x800 home=/p/p16-check/home cuts=/p/p16-check/cuts
    python scripts/shots.py after 390x844 --dark home=/p/p16-check/home

Waits until the page shows no "Loading…" and the network is quiet, then saves
docs/runs/img/<prefix>-<name>-<width>.png. --base picks the studio (default http://127.0.0.1:8770).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
READY = """(() => !document.body.innerText.includes('Loading…') && document.readyState === 'complete'
  && !document.querySelector('.skeleton'))()"""


async def shoot(ws_url: str, url: str, w: int, h: int, dark: bool, out: Path, settle: float) -> None:
    async with websockets.connect(ws_url, max_size=64 * 2**20) as ws:
        n = 0

        async def call(method: str, **params):
            nonlocal n
            n += 1
            await ws.send(json.dumps({"id": n, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == n:
                    return msg.get("result", {})

        await call("Page.enable")
        await call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=w < 600)
        await call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark" if dark else "light"}])
        await call("Page.navigate", url=url)
        t0 = time.time()
        await asyncio.sleep(1.0)
        while time.time() - t0 < 25:
            r = await call("Runtime.evaluate", expression=READY, returnByValue=True)
            if r.get("result", {}).get("value"):
                break
            await asyncio.sleep(0.4)
        await asyncio.sleep(settle)
        shot = await call("Page.captureScreenshot", format="png")
        out.write_bytes(base64.b64decode(shot["data"]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prefix")
    ap.add_argument("size")
    ap.add_argument("pages", nargs="+", help="name=#hash-path")
    ap.add_argument("--base", default="http://127.0.0.1:8770")
    ap.add_argument("--out", default="docs/runs/img")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--settle", type=float, default=1.5)
    a = ap.parse_args()
    w, h = (int(x) for x in a.size.split("x"))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    port = 9333
    prof = tempfile.mkdtemp(prefix="recomp-shots-")
    proc = subprocess.Popen([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--remote-debugging-port={port}",
                             f"--user-data-dir={prof}", f"--window-size={w},{h}", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        for item in a.pages:
            name, path = item.split("=", 1)
            dest = out / f"{a.prefix}-{name}-{w}.png"
            asyncio.run(shoot(page["webSocketDebuggerUrl"], f"{a.base}/#{path}", w, h, a.dark, dest, a.settle))
            print(dest)
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
