# Autocheck.kz — 1C Dealer Feed Integration MVP

## What this project is
A microservice that ingests 1C export files from partner car dealerships, parses
them, upserts vehicles into SQLite by VIN, and exposes the result on a simple web page.
This is a **test assignment** graded on: prompt engineering, speed, and architectural
control — not on feature count. Scope discipline beats ambition.

## Stack (fixed — do not substitute)
- **Backend:** FastAPI + SQLModel + SQLite, Pydantic v2, APScheduler for cron
- **Frontend:** React + Vite + TypeScript
- **Tests:** pytest
- **Run:** `docker compose up` must be the single command that starts everything

## Non-negotiable requirements (from TASK.md)
1. Realistic generated dataset imitating a 1C export (VIN, brand, model, year,
   mileage, price, defects, dealer, export timestamp). Ship it as a committed
   fixture file, not generated at runtime only.
2. Two ingest triggers, both hitting the **same** ingest service function:
   - scheduled (cron/interval job)
   - forced via `POST /api/ingest` (webhook)
3. Web page listing loaded vehicles.
4. `README.md` — quick start, Docker-first.
5. `AI_LOGS.md` — the prompt log. **This is a graded deliverable, not an afterthought.**
6. **Bonus (do it):** upsert by VIN with no duplicates + unit tests proving it.

## Architecture rules
- One ingest path. Cron and webhook are thin callers of `services/ingest.py`.
  Never duplicate parsing logic per trigger.
- Parser is pure: file bytes/path in → validated Pydantic records out. No DB access
  inside the parser. This is what makes it unit-testable without a database.
- `vin` is the natural key: `UNIQUE` constraint at the DB level, not just app logic.
  Upsert = SQLite `INSERT ... ON CONFLICT(vin) DO UPDATE`.
- Every ingest run writes an `IngestRun` row (trigger source, counts of
  created/updated/skipped, errors, duration). The frontend shows the last run —
  this is the cheapest way to make the demo look real.
- Malformed rows never abort a run. Collect them, report them in the run summary.
- Config via env vars with sane defaults (`DATABASE_URL`, `INGEST_CRON_SECONDS`,
  `FEED_PATH`). No hardcoded absolute paths.

## Working agreement
- **Explore → Plan → Implement → Verify → Commit.** Small runnable increments.
- Never claim something works without running it. "Verified" means a command ran
  and its output is in the transcript: `pytest`, `docker compose up` + a real
  `curl` against the endpoint, and the page loaded in a browser.
- TDD for the upsert logic specifically: write the failing duplicate-VIN test first.
- Commit after each working increment. Conventional commit messages.
- Do not add auth, pagination libraries, Postgres, Redis, Celery, or a component
  library. Out of scope. If tempted, ask first.

## AI_LOGS.md protocol
After each meaningful work chunk, append a section to `AI_LOGS.md`:
```
## <n>. <what was asked>
**Prompt:** <the user's actual instruction, verbatim or near-verbatim>
**What the AI did:** <brief>
**Issues / corrections:** <what broke, how it was diagnosed and fixed — keep this honest, debugging history is explicitly graded>
```
Do not sanitize the log into a success story. The evaluator wants to see the
decomposition and the debugging, including dead ends.

## Skills to use
- `fastapi` — before writing backend code
- `vercel-react-best-practices` + `frontend-design` — before writing the UI
- `multi-stage-dockerfile` — for the Dockerfiles
- `pytest-coverage` — for the test pass
- `superpowers:test-driven-development` — for the upsert bonus
- `superpowers:verification-before-completion` — before any "it's done" claim
