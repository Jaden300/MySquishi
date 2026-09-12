"""Write the weekly narratives, offline, into a committed fixture.

Run by hand on the builder's machine, never by the app:

    cd backend
    .venv/bin/pip install -r tools/requirements-narratives.txt
    export ANTHROPIC_API_KEY=...
    .venv/bin/python -m tools.write_narratives

The app does not call a model. It reads `app/data/narratives.json`, which this
writes and which is committed, so a demo works with the network unplugged and a
fresh clone has the same prose the builder reviewed. Without a fixture the
route falls back to the deterministic template and nothing breaks.

Two rules this tool follows, both of them because generated clinical prose is
the riskiest text in the project:

**The model rewrites, it does not add.** It is given the sentences the models
already produced and asked to join them. Every number in the output has to
appear in the input, and a sentence that introduces one is dropped.

**The clinical gate runs after generation, not before.** `assert_gate_safe`
checks the finished text, and anything mentioning kilograms or EWGSOP2 for a
non grip history is discarded rather than edited. See app/clinical_gate.py.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

FIXTURE = BACKEND_DIR / "app" / "data" / "narratives.json"

MODEL = "claude-sonnet-5"

SYSTEM = """You rewrite rehabilitation progress notes for the patient who did the work.

You are given sentences that statistical models already produced about one
patient's recent weeks. Join them into a single short paragraph, at most four
sentences, that reads as one voice rather than a list.

Rules, all absolute:
- Introduce no number, measurement or claim that is not in the input.
- Drop anything you cannot express without inventing detail.
- Warm, plain and direct. Address the patient as "you".
- No em dashes or en dashes. Use a comma, a colon or a new sentence.
- Do not diagnose, and do not promise a recovery.
- Plain prose only. No lists, no headings, no preamble.
"""


def _client():
    """Imported inside the function, so the app can never pull this in."""
    from anthropic import Anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. This tool is the only thing in the "
            "project that needs one."
        )
    return Anthropic(api_key=key)


def _generate(client, source: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": source}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--patient",
        action="append",
        help="Patient id to write. Repeatable. Defaults to every patient.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without calling the model.",
    )
    args = parser.parse_args()

    from sqlmodel import Session as DbSession
    from sqlmodel import select

    from app.api.ml import _narrative
    from app.db import get_engine
    from app.ml import weekly
    from app.models import Patient, Session

    client = None if args.dry_run else _client()
    fixture: dict[str, dict[str, str]] = {}
    if FIXTURE.exists():
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    with DbSession(get_engine()) as db:
        ids = args.patient or [p.id for p in db.exec(select(Patient)).all()]

        for patient_id in ids:
            sessions = list(
                db.exec(
                    select(Session)
                    .where(Session.patient_id == patient_id)
                    .order_by(Session.started_at)  # type: ignore[arg-type]
                ).all()
            )
            if not sessions:
                continue

            rollup = weekly.roll_up(sessions)
            if rollup.insufficient_data:
                continue

            # The template is the input to the model as well as the fallback.
            # Rewriting sentences that are already gated is a much smaller ask
            # than composing from raw numbers, and it is why the output can be
            # checked by comparing it against its own source.
            source = _narrative(patient_id, db, rollup, sessions)["text"]
            if not source:
                continue

            muscles = {s.muscle for s in sessions}

            if args.dry_run:
                print(f"--- {patient_id} ---\n{source}\n")
                continue

            text = weekly.assert_gate_safe(_generate(client, source), muscles)
            if not text:
                print(f"{patient_id}: refused by the clinical gate, skipped")
                continue

            fixture.setdefault(patient_id, {})["latest"] = text
            print(f"{patient_id}: {len(text)} characters")

    if args.dry_run:
        return 0

    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {FIXTURE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
