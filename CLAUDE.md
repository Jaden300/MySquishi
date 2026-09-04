# MySquishi

Grip-strength rehabilitation companion. sEMG (MyoWare + Arduino) -> FastAPI/scikit-learn -> React dashboard.

**Read `@docs/WORKFLOW.md` before starting any task.** It defines how agents work in this repo.

## Stack

- Frontend: React + Vite + TypeScript + Tailwind, Recharts, Zustand, Framer Motion (mascot only)
- Backend: FastAPI + SQLModel/SQLite, scikit-learn, SciPy, NumPy, Pandas

## Non-negotiables

1. **The app must be fully demoable with zero hardware attached.** Hardware is an enhancement layer, never a dependency.
2. **Phase 2 (hardware bring-up) is a hard stop.** It requires the builder physically present. Do not proceed past it autonomously.
3. Clinical terminology must be accurate. See `@docs/CLINICAL.md`.
4. No bare point estimates; synthetic data is labeled synthetic in the UI.
5. **No em dashes or en dashes anywhere.** Not in code, comments, UI copy, docs, or commit messages. Use a hyphen, a colon, or a new sentence instead.
6. **Never credit Claude or any AI as an author or contributor.** No `Co-Authored-By` trailers, no "Generated with" lines, in commits or PR descriptions.

## Docs

`docs/WORKFLOW.md` · `TASKS.md` · `ARCHITECTURE.md` · `DESIGN.md` · `CLINICAL.md` · `ML.md` · `HARDWARE_CHECKLIST.md`

Pull in with `@docs/<file>.md` when the task needs it. Keep this file minimal.
