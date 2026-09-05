"""API routers.

One module per resource. `register_routers` is the single wiring point, so
main.py stays a description of the application rather than a list of imports.
"""

from __future__ import annotations

from fastapi import FastAPI


def register_routers(app: FastAPI) -> None:
    """Attach every router to the application.

    Imported inside the function so that a router still under construction
    cannot break application import at module load.
    """
    from app.api import patients, sessions, signal

    for module in (patients, sessions, signal):
        app.include_router(module.router)

    # Routers that arrive with their model slices. Missing ones are skipped
    # rather than fatal, so the spine stays runnable while they land.
    for name in ("ml", "cohort", "export"):
        try:
            module = __import__(f"app.api.{name}", fromlist=["router"])
        except ImportError:
            continue
        app.include_router(module.router)


__all__ = ["register_routers"]
