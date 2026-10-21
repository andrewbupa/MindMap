# Runbook

How to run Bench locally, set it up on DigitalOcean, deploy it, and look after it.
Updated at the end of each milestone. Last updated: milestone 4.

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

Locally, agents answer through Bench's development model (`benchdev/scripted`),
which needs no provider key. To use real models, set `BENCH_MODELS_FILE` to
`/app/config/models.yaml` and `ANTHROPIC_API_KEY` in `.env.compose` (compose) or
`.env` (without Docker).

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
| `make seed-demo` | Scan synthetic content, create the bucket, and load `agents/` |

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
   | `ANTHROPIC_API_KEY` | The Anthropic console; one key per environment |
   | `OPENAI_API_KEY` | The OpenAI platform; for the Lens panel's second judge |

5. **Keep secrets in the spec encrypted.** Run `doctl apps spec get <app-id>` and
   copy the `EV[...]` values it shows into `.do/app.yaml`, so later `doctl apps
   update` calls keep them. Never commit a plaintext secret.
6. **First deploy.** Merge to `main`. Then follow "After every deploy" below.

## Deploying

Every push to `main` deploys. App Platform builds both images, runs the `migrate`
job (`python -m bench_worker.cli migrate`: Alembic migrations, then the agent
registry sync), and only if it succeeds replaces the services and the worker. A failed migration should stop the deploy and leave the previous
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

**Adding a prompt version.** Add `agents/<agent>/prompts/v<n>.md` with front matter
(`version`, `author`, `notes`) and merge. Never edit a version that has been
deployed: the deploy will fail, by design, until the edit becomes a new file.

**A tool needs Bench to call an agent.** An admin creates an API token in
Settings, API tokens, and hands it over as a secret. The tool calls
`https://<app-domain>/api/v1/agents/<agent>/<version>/chat/completions` with
`Authorization: Bearer <token>`. Revoke tokens that are no longer needed.

**Running an audit.** Explore, Start an audit: pick an agent version and seeds.
Each seed at each repetition runs as its own job; the page updates as samples
finish. Samples on one worker run one at a time, because Inspect allows one eval
per process; raise the worker's `instance_count` in `.do/app.yaml` to run more
at once.

**An audit seems stuck.** Check `run_sample` for the run: `heartbeat_at` moves
every 20 seconds while a sample runs. A sample whose worker died is re-queued
within a minute. A sample that failed twice stays failed with its error.

**Adding a seed or rubric.** Add a markdown file to `seeds/petri/seeds/` or
`seeds/petri/dimensions/` and merge. Runs already launched keep the versions they
recorded; a sample whose seed changed under it fails rather than run the new text.

**Opening a sample in Inspect View.** On a transcript page, download the Inspect
log, then run `inspect view --log-dir <folder>` locally.

**Measuring a behaviour.** Measure, then the behaviour, then "Generate scenarios".
Generation is one job: Bloom writes its understanding of the behaviour, then the
scenarios and a variation of each. It is stored once and never changes. Then
"Start a suite on this scenario set": choose the prompt versions and repetitions
(three by default). Each scenario at each repetition runs as its own job, and the
behaviour page charts the newest finished run per prompt version. Cite a rate
with its run's seed hash.

**Changing a behaviour.** Edit `seeds/bloom/<behaviour>/BEHAVIOR.md` and merge.
That is a new behaviour version with no scenarios: generate a new set, and rerun
suites on it. Earlier sets and their rates stay readable but are not compared
with the new ones. Never commit a `scenarios/` folder there; Bench refuses it.

**A generation failed.** Its error is on the behaviour page, under generation runs.
"Look like they contain real personal data" means the synthetic-data scan caught
something in what the model wrote; generate again, and if it repeats, tighten the
behaviour's `instructions.ideation`.

**The audit log** is append-only in Postgres. Compliance and admins read it in
Settings, audit log.

## Model providers and retention

Every auditor, target and judge call sends content to a provider. Record each
provider's retention terms here before it is used, and use zero data retention
arrangements where available. Bench sends only synthetic content until an admin
approves an import.

| Provider | Used for | Retention terms | Zero data retention | Confirmed by, date |
| --- | --- | --- | --- | --- |
| Anthropic | Target, auditor, judge A, scanner, Bloom scenarios (`config/models.yaml`) | To confirm for our account | To confirm. Claude Fable 5.1 is not available under zero data retention | |
| OpenAI | Judge B on the Lens panel (`openai/gpt-6.1-sol`) | To confirm for our account | To confirm | |

## Milestone status

### Milestone 4: measure

Built: five behaviours in `seeds/bloom/` in petri_bloom 0.2.6's format; scenario
generation as a one-job run whose output is a write-once scenario set; suites of
one run per prompt version, with a job per scenario and repetition that runs
Bloom's own task with its auditor aimed at Bench's Petri target, so the agent's
real prompt stays fixed; rollouts indexed into the shared transcript and score
tables; elicitation rates with each repetition's rate and their range; the
behaviour page with its rate chart and table, the highest-scoring transcripts,
the scenario set page, the suite form and the run page.

Verified: in the tests, generation with the development model (six scenarios,
one presence dimension, a read-only set) and a two-repetition suite with
scripted judges (rate 5 of 12, repetitions 50% and 33%, our prompt in the
target's system message, Bloom's task in the log); refusals for a changed
behaviour, a changed scenario set and an agent the behaviour is not for. In a
browser with the development model: generation, a two-version suite run by the
worker, and the chart, tables, run page and transcript in light and dark.

Waiting on: an Anthropic key in production, to generate real scenarios and run
suites with real models; answers to the open questions in docs/DECISIONS.md.

### Milestone 3: explore

Built: 21 seeds and six judge rubrics in git; Petri 3.1.1 audits of an agent
version, one sample per job, with our real prompt and tools inside Petri's
target protocol; per-sample logs in Spaces; indexed conversations, judge
summaries, highlights and scores; the launch form, live progress, the dimension
heatmap and the transcript reader with every citation linked.

Verified: a real Petri audit with scripted auditor, target and judge models in
the tests (the target received our prompt with the auditor's text in the context
block, a fixture answered its tool call, all 44 dimensions were indexed and
citations resolved); and in a browser with the development model, a three-seed
audit from launch to heatmap to transcript to downloaded log.

Waiting on: an Anthropic key in production, to run audits with real models.

### Milestone 2: agents and adapter

Built: two synthetic agents in git with prompt versions, tools, fixtures and
personas; the registry sync; model roles; the personal-data scan; the adapter in
deployed and open modes; Inspect transcripts in Spaces; the agents area with
side-by-side prompt diffs; the playground; API tokens and the OpenAI-compatible
endpoint.

Verified locally in a browser with the development model: an author picks
claims assistant v2 and a persona, chats, the agent looks up a claim through a
fixture, the thinking summary shows in its own pane, finishing saves the run,
and the downloaded `.eval` file opens in Inspect with the run's provenance. The
endpoint is covered by API tests.

Waiting on: an Anthropic key in production, to try real models; and the
production setup from milestone 1.

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
