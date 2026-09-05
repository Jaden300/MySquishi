"""Standalone operator tools that live outside the FastAPI application.

Nothing under `app/` may import from here, and nothing here is needed to run
the app. The separation is deliberate: `tools/` is where hardware-facing code
is allowed to exist, while `app/` stays serial free through Phase 1 and 2. The
guard tests in `app/tests/` scope their no-serial-imports check to `app/`
precisely so this directory can hold the Phase 2 bring up probe.
"""
