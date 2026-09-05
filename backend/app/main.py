"""FastAPI application entry point.

Run with:
    backend/.venv/bin/uvicorn app.main:app --reload --port 8000
from the backend directory.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import register_routers
from app.api.live import FRAME_KEYS
from app.config import settings
from app.db import create_db_and_tables


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
