"""Capture the README screenshots.

Drives headless Chrome over the DevTools protocol. No new dependency: Chrome
is already on the machine and websockets already ships with the backend.

Chrome's own --screenshot flag is not used, and the reason is worth recording.
It honours --window-size for the image but not for layout, so a capture at
390px comes back looking like a broken 440px page: the nav clipped, cards
running past the gutter. Setting the viewport through
Emulation.setDeviceMetricsOverride is what actually makes the page believe it
is on a phone. The overflow that flag appeared to show was a real bug the
first time, so the distinction matters.

Run the app first, then this:

    .venv/bin/uvicorn app.main:app --port 8090
    .venv/bin/python -m tools.screenshots

The frontend must be built (`cd frontend && npm run build`), since the backend
serves `frontend/dist`. Writes PNGs to docs/images/.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9333
REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "docs" / "images"

# One per thing the README actually shows. Kept short: a screenshot nobody
# looks at is a file to keep up to date for nothing.
#
# The live session is the one that needs driving rather than just loading. A
# plain capture of /train?stage=live catches the page before anything starts,
# so the oscilloscope is empty and the shot argues against the feature it is
# meant to show. `start` clicks Start session and waits for the stream, so the
# trace, the coach and the repetition count are all real.
SHOTS: tuple[tuple[str, str, bool], ...] = (
    ("train", "/train?stage=live", True),
    ("progress", "/progress", False),
    ("lab", "/lab?tab=clinician", False),
    ("hardware", "/lab?tab=hardware", False),
)

# Long enough for the generator to produce a contraction, a release and at
# least one counted repetition.
SESSION_S = 14.0

START_SESSION = (
    "[...document.querySelectorAll('button')]"
    ".find(b => /start session/i.test(b.textContent))?.click()"
)

DESKTOP = {"width": 1280, "height": 860, "deviceScaleFactor": 2, "mobile": False}
MOBILE = {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True}

# Recharts has to lay out and Framer Motion has to settle. Shorter than this
# and charts land half drawn.
SETTLE_S = 6.0


class Devtools:
    """A very small DevTools client. Enough to navigate and capture."""

    def __init__(self, ws_url: str) -> None:
        from websockets.sync.client import connect

        # legacy=True because this client is held open across many navigations
        # rather than used as a context manager for one exchange.
        self._ws = connect(ws_url, max_size=None, legacy=True)
        self._id = 0

    def __enter__(self) -> Devtools:
        return self

    def __exit__(self, *exc: object) -> None:
        self._ws.close()

    def send(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        self._ws.send(
            json.dumps({"id": self._id, "method": method, "params": params or {}})
        )
        while True:
            message = json.loads(self._ws.recv())
            if message.get("id") == self._id:
                return message.get("result", {})


def _page_target() -> str:
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json"))
    pages = [t for t in tabs if t.get("type") == "page"]
    if not pages:
        raise RuntimeError("Chrome is running but has no page target.")
    return pages[0]["webSocketDebuggerUrl"]


def _start_chrome() -> subprocess.Popen[bytes]:
    process = subprocess.Popen(
        [
            CHROME,
            "--headless",
            "--disable-gpu",
            f"--remote-debugging-port={DEBUG_PORT}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version")
            return process
        except (urllib.error.URLError, ConnectionError):
            time.sleep(0.25)

    process.terminate()
    raise RuntimeError("Chrome did not open a debugging port.")


def capture(base_url: str, mobile: bool = False) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    chrome = _start_chrome()

    try:
        with Devtools(_page_target()) as dev:
            dev.send(
                "Emulation.setDeviceMetricsOverride", MOBILE if mobile else DESKTOP
            )

            for name, path, start in SHOTS:
                dev.send("Page.navigate", {"url": base_url + path})
                time.sleep(SETTLE_S)

                if start:
                    dev.send("Runtime.evaluate", {"expression": START_SESSION})
                    time.sleep(SESSION_S)

                shot = dev.send("Page.captureScreenshot", {"format": "png"})
                suffix = "-mobile" if mobile else ""
                out = OUT_DIR / f"{name}{suffix}.png"
                out.write_bytes(base64.b64decode(shot["data"]))
                written.append(out)
                print(f"  {out.relative_to(REPO_ROOT)}")
    finally:
        chrome.terminate()

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8090",
        help="where the app is served (default: %(default)s)",
    )
    parser.add_argument(
        "--mobile",
        action="store_true",
        help="capture at 390px instead of 1280px",
    )
    args = parser.parse_args()

    try:
        urllib.request.urlopen(args.base_url + "/api/health", timeout=5)
    except Exception as exc:
        raise SystemExit(
            f"Nothing answering at {args.base_url}. Start the app first:\n"
            "  cd frontend && npm run build\n"
            "  cd backend && .venv/bin/uvicorn app.main:app --port 8090"
        ) from exc

    print(f"Capturing from {args.base_url}")
    capture(args.base_url, mobile=args.mobile)


if __name__ == "__main__":
    main()
