"""FastAPI application entry point.

Run with:
    backend/.venv/bin/uvicorn app.main:app --reload --port 8000
from the backend directory.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
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


@app.get("/api/health")
def health() -> dict[str, object]:
    """Liveness probe, also reporting the acquisition constants the frontend
    needs in order to size its buffers."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "sample_rate": settings.sample_rate,
        "window_samples": settings.window_samples,
    }
