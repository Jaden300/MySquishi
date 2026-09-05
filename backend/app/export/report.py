"""The clinician PDF report. Phase 4.

Deliberately a stub rather than a half implementation. docs/TASKS.md places
the PDF export in Phase 4, and the CSV export covers the same data today.
"""

from __future__ import annotations


def build_report(patient_id: str) -> bytes:
    """Render a clinician report as PDF."""
    raise NotImplementedError(
        "The PDF report arrives in Phase 4. Use app.export.csv_export for the "
        "same data today."
    )


__all__ = ["build_report"]
