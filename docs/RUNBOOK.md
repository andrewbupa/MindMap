# Runbook

How to run Bench locally, set it up on DigitalOcean, deploy it, and look after it.
Updated at the end of each milestone. Last updated: milestone 1.

## Local development

### With Docker (recommended)

```sh
make dev
```

Then open <http://bench.localhost:3000>. The stack is Postgres 17, SeaweedFS for
storage, a mock identity provider, the API, the worker, the web app, and Caddy in
front routing `/api` to the API as App Platform's ingress does.

To sign in, type any username into the mock provider's form and put this in the
claims box:

```json
{ "email": "admin@example.test", "name": "Ada Admin" }
```

`admin@example.test` is a bootstrap admin locally. Any other email signs in with
no role until an admin grants one in Settings, users.

`make dev-down` stops everything and keeps data. Signed URLs open on
`http://localhost:8333`, where compose publishes SeaweedFS.

### Without Docker

You need Python 3.12, uv, Node 22.18 or later, and Postgres.

```sh
cp .env.example .env
cd python && uv sync && uv run alembic upgrade head
uv run moto_server -p 9000 &                    # S3 stand-in
uv run python -m bench_worker.cli ensure-bucket
uv run uvicorn bench_api.main:app --port 8000 &
uv run procrastinate --app=bench_worker.app.app worker &
cd ../web && npm ci && npm run dev              # forwards /api to port 8000
```

For sign-in, run the mock identity provider on port 8080 (`docker run -p
8080:8080 -e JSON_CONFIG="$(cat infra/dev/mock-oidc.json)"
ghcr.io/navikt/mock-oauth2-server:6.1.2`), then open <http://localhost:3000>.

### Everyday commands

| Command | What it does |
| --- | --- |
| `make lint` | ruff, mypy (strict in `bench_core`), ESLint and the TypeScript check |
| `make test` | pytest against `bench_test`; needs Postgres |
| `make migrate` | Alembic migrations against `BENCH_DATABASE_URL` |
| `make openapi` | Regenerate `web/lib/api` from the API schema |
| `make spec` | Check `.do/app.yaml` against App Platform's schema |
| `make seed-demo` | Load synthetic demo data (agents arrive in milestone 2) |

Tests expect a database `bench_test` owned by user `bench` (password `bench`) on
`localhost:5432`, or set `BENCH_DATABASE_URL`. They migrate it from scratch.

## Production setup (once)

Do these in order. Everything lives in the Sydney region.

1. **Database.** Create a managed Postgres 17 cluster named `bench-pg` in `syd1`.
   In the control panel, create the database `bench` and the user `bench` (create
   the user there, not with SQL, or App Platform cannot read its password). Turn
   on trusted sources; attaching the cluster to the app adds the app
   automatically. Managed Postgres takes daily backups with point-in-time
   recovery; confirm the retention period suits us.
2. **Spaces.** Create a private bucket `bench-logs` in `syd1` with file listing
   restricted. Create a Spaces access key limited to that bucket.
3. **Identity provider.** Register Bench as a confidential OpenID Connect client:
   - redirect URI `https://<app-domain>/api/auth/callback`
   - sign-out redirect `https://<app-domain>/signed-out`
   - scopes `openid profile email`, plus a `groups` claim if roles come from groups
4. **App.** `doctl apps create --spec .do/app.yaml`, then connect the GitHub
   repository when prompted. Set the values marked `set-me` or empty in the spec,
   and set every secret in the control panel:

   | Variable | Where it comes from |
   | --- | --- |
   | `BENCH_SPACES_KEY`, `BENCH_SPACES_SECRET` | The Spaces access key |
   | `BENCH_OIDC_CLIENT_SECRET` | The identity provider registration |
   | `BENCH_SESSION_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `BENCH_OIDC_METADATA_URL`, `BENCH_OIDC_CLIENT_ID` | The identity provider registration (not secret) |
   | `BENCH_BOOTSTRAP_ADMINS` | Comma-separated emails of the first admins |
   | `BENCH_OIDC_ROLE_MAP` | Optional JSON, e.g. `{"bench-reviewers": "reviewer"}` |

5. **Keep secrets in the spec encrypted.** Run `doctl apps spec get <app-id>` and
   copy the `EV[...]` values it shows into `.do/app.yaml`, so later `doctl apps
   update` calls keep them. Never commit a plaintext secret.
6. **First deploy.** Merge to `main`. Then follow "After every deploy" below.

## Deploying

Every push to `main` deploys. App Platform builds both images, runs the `migrate`
job (`alembic upgrade head`), and only if it succeeds replaces the services and
the worker. A failed migration should stop the deploy and leave the previous
version running; answers on DigitalOcean's community forum say so, though the job docs
do not. Confirm this on the first deploy that carries a migration.

Spec changes are not picked up from git: apply them with `doctl apps update
<app-id> --spec .do/app.yaml` after merging.

### After every deploy

1. Open Settings, system checks, and run a check. It should reach "Succeeded"
   within a few seconds, and its object link should open the JSON the worker wrote.
2. Check `/api/health` shows the commit you merged.

### Rolling back

Use "Rollback" on a previous deployment in the control panel. Migrations only
move forward in production; if a migration must be undone, write a new one.

## Looking after it

**A job seems stuck.** Jobs left running by a worker that died are re-queued
within a minute by `retry_stalled_jobs`. To look directly:

```sql
SELECT id, task_name, status, attempts, scheduled_at FROM procrastinate_jobs
WHERE status IN ('todo', 'doing', 'failed') ORDER BY id DESC LIMIT 20;
```

**Someone has left.** Deactivate them in Settings, users. Their sessions end at
once. If roles come from identity-provider groups, remove them there too.

**Rotating the session secret** signs nobody out: it protects only the ten-minute
OAuth state cookie. Sessions themselves live in Postgres; to end them all, run
`DELETE FROM user_session;`.

**Upgrading Procrastinate.** See docs/DECISIONS.md: add an Alembic revision that
applies its new SQL migration files, then bump the version pin.

**The audit log** is append-only in Postgres. Compliance and admins read it in
Settings, audit log.

## Model providers and retention

Every auditor, target and judge call sends content to a provider. Record each
provider's retention terms here before it is used, and use zero data retention
arrangements where available. Bench sends only synthetic content until an admin
approves an import.

| Provider | Used for | Retention terms | Zero data retention | Confirmed by, date |
| --- | --- | --- | --- | --- |
| Anthropic | To be set in milestone 2 | To confirm | To confirm | |
| Second judge family | To be chosen in milestone 5 | To confirm | To confirm | |

## Milestone status

### Milestone 1: foundations

Built: monorepo, uv workspace, Next.js shell, full schema and migrations,
read-only guards, Spaces storage with signed URLs, sign-in with roles, the
Postgres queue and worker, the app spec, CI, and local development.

Verified locally, in a browser, against the docker-compose stack: sign-in through
the mock identity provider, roles and the admin pages, a system check completed
by the worker with its object opened from storage through a signed URL, the
audit log, and sign-out. The images run the migrate, API and worker commands as
App Platform will.

Waiting on production setup (above) to meet the milestone's "done" line on
DigitalOcean: the deployed app signing people in, migrations running before
deploy, and a system check writing to Spaces.
