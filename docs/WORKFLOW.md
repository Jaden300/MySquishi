# Workflow conventions

**Every Claude agent working in this repo follows this structure. Read it before starting a task.**

Keep CLAUDE.md minimal - Only include what's needed in EVERY session
Use /clear for new tasks - Don't use /compact unless you really need the context
Iterate over small changes - When done, /clear
Store project knowledge in docs/ - Reference with @docs/filename.md when needed
Memory Bank? - Probably not worth it. Use docs/ instead.
Track tasks with checkboxes - Use [ ] in markdown files instead of complex memory systems

---

## What this means in practice

**CLAUDE.md is a pointer, not a manual.** It holds only what is true in every single session: the stack, the run commands, and a map of `docs/`. Anything task-specific goes in `docs/` and gets pulled in with `@docs/filename.md` when that task comes up. If you learn something durable while working, write it to the right file in `docs/`. Do not grow CLAUDE.md.

**One task per context.** Finish a small unit of work, verify it, then `/clear`. Reach for `/compact` only when a task genuinely cannot be split and the context is still needed.

**Small changes, verified.** Prefer a working slice over a large half-finished one. Every phase in the build plan is decomposable. Pick the smallest piece that can be run and checked.

**Tasks are checkboxes in markdown.** Progress lives in `docs/TASKS.md` as `- [ ]` / `- [x]`. Update it as work completes. No external tracker, no memory-bank system.

## Writing conventions

**No em dashes or en dashes. Anywhere.** This is absolute and applies to every character an agent writes in this repo:

- source code, identifiers, string literals, and comments
- all user-facing frontend copy, labels, tooltips, and error messages
- every markdown file in `docs/`, plus `CLAUDE.md` and `README`
- git commit messages, branch names, and PR titles and descriptions
- test fixtures and seed data

Use a hyphen (`-`) where a dash is needed. Often a colon, a comma, parentheses, or splitting into two sentences reads better. The same goes for ranges: write `M1-M14` and `0-100`, never with an en dash.

Before committing, check nothing slipped in:

```bash
grep -rn '[—–]' . --exclude-dir=.git --exclude-dir=node_modules
```

## Attribution conventions

**Never list Claude, Anthropic, or any AI as an author or contributor.** When committing or pushing:

- no `Co-Authored-By: Claude ...` trailer
- no "Generated with Claude Code" line or similar
- no AI mention in PR descriptions, changelogs, or release notes

Commits are authored by the builder alone. Write the commit message as a plain description of the change.

## docs/ map

| File | Holds |
|---|---|
| `WORKFLOW.md` | This file: how agents work in this repo |
| `TASKS.md` | The checkbox task board, grouped by build phase |
| `ARCHITECTURE.md` | System design, the `SignalSource` boundary, module layout |
| `DESIGN.md` | Palette tokens, typography, Squishi, copy voice, a11y floor |
| `CLINICAL.md` | Clinical terminology reference, definitions must be accurate |
| `ML.md` | The M1-M14 model stack, inputs/outputs, explainability |
| `HARDWARE_CHECKLIST.md` | Phase 2 bring-up: wiring, electrode placement, test protocol |

The private build plan (`MySquishi_Plan.md`, gitignored) is the source of truth for *what* to build. `docs/` is the working reference for *how*.

## Hard rules from the plan

- **Phase 1 ships with zero hardware.** Do not write serial-port code before Phase 2.
- **PHASE 2 IS A HARD STOP.** Hardware bring-up requires the builder physically present. Do not proceed autonomously past it.
- Simulation Mode is a permanent first-class feature, not a fallback.
- Synthetic data is labeled as synthetic **in the UI**.
- No bare point estimates. Every prediction ships with an interval.
