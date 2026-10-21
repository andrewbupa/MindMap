# Bench

Internal platform that tests our AI agents three ways: Explore (Petri 3),
Measure (Bloom) and Lens (expressed dispositions, read from text).
Full brief: docs/BRIEF.md. Read it before starting any milestone.

## How we work
- Plan each milestone, list open questions, and wait for approval before coding.
- Build each milestone completely, deploy it, then update docs/RUNBOOK.md.
- Record every design choice and every place the brief and a library disagree
  in docs/DECISIONS.md. Current library documentation beats the brief.
- Pin versions of inspect-ai, inspect-petri, inspect-scout and bloom.
  Read their current docs before integrating; never guess an API.

## Stack
- Python 3.12, uv workspace in python/, ruff, mypy (strict in bench_core).
- FastAPI, SQLAlchemy 2, Alembic, Procrastinate (Postgres-backed queue).
- Next.js App Router, strict TypeScript, API client generated from OpenAPI.
- Deploy: DigitalOcean App Platform via .do/app.yaml; logs in Spaces.

## Rules that never bend
- No secrets in the repository. No real personal or health data in fixtures,
  seeds, tests or screenshots: everything is synthetic.
- Finished runs are read-only. Every run stores git commit, config hash,
  prompt SHA, seed hash, taxonomy version and resolved model IDs.
- Lens findings must quote the transcript exactly; verify quotes in code
  and drop any that do not match.
- Label thinking summaries as summaries. Never prompt a target model to
  narrate its reasoning in its visible answer.
- No model family judges its own outputs alone.
- Containers have temporary disks: anything worth keeping goes to Postgres
  or Spaces.

## Interface
- Design tokens live in web/styles/tokens.css; components in
  web/components/ui come from Claude Design handoffs in design/.
- Every number on screen links to the evidence behind it.
- Copy: plain British English, short sentences, sentence-case labels.

## Commands
- make dev, make migrate, make lint, make test, make seed-demo
