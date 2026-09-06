"""FastAPI application entry point.

Run with:
    backend/.venv/bin/uvicorn app.main:app --reload --port 8000
from the backend directory.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import register_routers
from app.api.live import FRAME_KEYS
from app.config import settings
from app.db import create_db_and_tables

# The Vite build, which a single service deployment serves alongside the API.
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    # Seed the demo account so the dashboard is never empty on first click.
    # Failing to seed must not stop the app from starting: an empty dashboard
    # with working empty states is a worse demo, not a broken one.
    try:
        from app.seed import seed_demo

        seed_demo()
    except Exception as exc:  # noqa: BLE001
        print(f"Demo seeding skipped: {exc}")

    yield


app = FastAPI(
    title="MySquishi",
    description=(
        "Grip strength rehabilitation companion. Not a medical device: "
        "MySquishi is a training aid and does not replace a clinician."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# The Vite dev server proxies /api, but direct browser access during
# development still needs these origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


register_routers(app)


@app.get("/api/health")
def health() -> dict[str, object]:
    """Liveness probe, also reporting the acquisition constants the frontend
    needs in order to size its buffers.

    frame_keys travels with it so the frontend can assert the websocket
    contract in a test rather than discovering a renamed field as undefined
    in a chart.
    """
    return {
        "status": "ok",
        "app": settings.app_name,
        "sample_rate": settings.sample_rate,
        "window_samples": settings.window_samples,
        "frame_keys": list(FRAME_KEYS),
    }


# Serving the built frontend is what makes this one deployable service, and it
# is why no API base URL or CORS origin has to be configured anywhere: the app
# and the API share an origin, so /api resolves and wss: is derived from https:.
#
# Registered last, after the routers above, so a real API route always wins over
# the catch-all. Absent build directory is the normal case for backend only
# development and for the test suite, so it must not be an error.
if FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Hand every non API path to the client router.

        App.tsx uses createBrowserRouter, so a deep link like /clinician is a
        real URL the server sees on a refresh. It has no file of its own: the
        router resolves it once index.html loads.
        """
        # An unmatched /api path is a missing endpoint. Returning the SPA shell
        # there would answer a bad request with 200 and a page of HTML, which
        # the fetch client would then fail to parse as JSON.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"No route '/{full_path}'.")

        # Files that sit at the root of the build: favicon.svg, logo.svg.
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and candidate.is_relative_to(FRONTEND_DIST.resolve())
        ):
            return FileResponse(candidate)

        return FileResponse(FRONTEND_DIST / "index.html")
