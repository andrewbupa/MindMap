# Runbook

How to run Agora locally, set it up on DigitalOcean, deploy it, and look after it.
Updated at the end of each milestone. Last updated: milestone 7.

## Local development

### With Docker (recommended)

```sh
make dev
```

Then open <http://agora.localhost:3000>. The stack is Postgres 17, SeaweedFS for
storage, a mock identity provider, the API, the worker, the web app, and Caddy in
front routing `/api` to the API as App Platform's ingress does.

To sign in, type any username into the mock provider's form and put this in the
claims box:

```json
{ "email": "admin@example.test", "name": "Ada Admin" }
```

`admin@example.test` is a bootstrap admin locally. Any other email signs in with
no role until an admin grants one in Settings, users.

Locally, agents answer through Agora's development model (`agoradev/scripted`),
which needs no provider key. To use real models, set `AGORA_MODELS_FILE` to
`/app/config/models.yaml` and `ANTHROPIC_API_KEY` in `.env.compose` (compose) or
`.env` (without Docker).

The local worker takes every queue, the witness's included, and reads with the
development lexicon reader (`AGORA_WITNESS_FILE=config/witness.dev.yaml`), so
open-model signals work without a GPU. Its values mean nothing about any model.

`make dev-down` stops everything and keeps data. Signed URLs open on
`http://localhost:8333`, where compose publishes SeaweedFS.

### Without Docker

You need Python 3.12, uv, Node 22.18 or later, and Postgres.

```sh
cp .env.example .env
cd python && uv sync && uv run alembic upgrade head
uv run moto_server -p 9000 &                    # S3 stand-in
uv run python -m agora_worker.cli ensure-bucket
uv run uvicorn agora_api.main:app --port 8000 &
uv run procrastinate --app=agora_worker.app.app worker &
cd ../web && npm ci && npm run dev              # forwards /api to port 8000
```

For sign-in, run the mock identity provider on port 8080 (`docker run -p
8080:8080 -e JSON_CONFIG="$(cat infra/dev/mock-oidc.json)"
ghcr.io/navikt/mock-oauth2-server:6.1.2`), then open <http://localhost:3000>.

### Everyday commands

| Command | What it does |
| --- | --- |
| `make lint` | ruff, mypy (strict in `agora_core`), ESLint and the TypeScript check |
| `make test` | pytest against `agora_test`; needs Postgres |
| `make migrate` | Alembic migrations against `AGORA_DATABASE_URL` |
| `make openapi` | Regenerate `web/lib/api` from the API schema |
| `make spec` | Check `.do/app.yaml` against App Platform's schema |
| `make seed-demo` | Scan synthetic content, create the bucket, and load `agents/` |

Tests expect a database `agora_test` owned by user `agora` (password `agora`) on
`localhost:5432`, or set `AGORA_DATABASE_URL`. They migrate it from scratch.

## Production setup (once)

Do these in order. Everything lives in the Sydney region.

1. **Database.** Create a managed Postgres 17 cluster named `agora-pg` in `syd1`.
   In the control panel, create the database `agora` and the user `agora` (create
   the user there, not with SQL, or App Platform cannot read its password). Turn
   on trusted sources; attaching the cluster to the app adds the app
   automatically. Managed Postgres takes daily backups with point-in-time
   recovery; confirm the retention period suits us.
2. **Spaces.** Create a private bucket `agora-logs` in `syd1` with file listing
   restricted. Create a Spaces access key limited to that bucket.
3. **Identity provider.** Register Agora as a confidential OpenID Connect client:
   - redirect URI `https://<app-domain>/api/auth/callback`
   - sign-out redirect `https://<app-domain>/signed-out`
   - scopes `openid profile email`, plus a `groups` claim if roles come from groups
4. **App.** Agora runs in the existing app `bupa-ai-poc`, which keeps its name and
   address; applying the spec replaces the earlier proof of concept's service.
   Give DigitalOcean's GitHub app access to `andrewbupa/agora`, then apply the spec
   in the control panel (Settings, App Spec) or with `doctl apps update <app-id>
   --spec .do/app.yaml`. Set the values marked `set-me` or empty in the spec, and
   set every secret in the control panel:

   | Variable | Where it comes from |
   | --- | --- |
   | `AGORA_SPACES_KEY`, `AGORA_SPACES_SECRET` | The Spaces access key |
   | `AGORA_OIDC_CLIENT_SECRET` | The identity provider registration |
   | `AGORA_SESSION_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
   | `AGORA_OIDC_METADATA_URL`, `AGORA_OIDC_CLIENT_ID` | The identity provider registration (not secret) |
   | `AGORA_BOOTSTRAP_ADMINS` | Comma-separated emails of the first admins |
   | `AGORA_OIDC_ROLE_MAP` | Optional JSON, e.g. `{"agora-reviewers": "reviewer"}` |
   | `ANTHROPIC_API_KEY` | The Anthropic console; one key per environment |
   | `OPENAI_API_KEY` | The OpenAI platform; for the Ethos panel's second judge |

5. **Keep secrets in the spec encrypted.** Run `doctl apps spec get <app-id>` and
   copy the `EV[...]` values it shows into `.do/app.yaml`, so later `doctl apps
   update` calls keep them. Never commit a plaintext secret.
6. **First deploy.** Merge to `main`. Then follow "After every deploy" below.
7. **Runner, when it is needed.** Witness readers (and Dish, later) run on a GPU
   Droplet that takes the `witness` and `sandbox` queues. Follow
   `infra/runner/README.md`. Until a runner exists, jobs on those queues wait.

## Deploying

Every push to `main` deploys. App Platform builds both images, runs the `migrate`
job (`python -m agora_worker.cli migrate`: Alembic migrations, then the agent
registry sync), and only if it succeeds replaces the services and the worker. A failed migration should stop the deploy and leave the previous
version running; answers on DigitalOcean's community forum say so, though the job docs
do not. Confirm this on the first deploy that carries a migration.

Spec changes are not picked up from git: apply them with `doctl apps update
<app-id> --spec .do/app.yaml` after merging.

The runner does not deploy itself. After App Platform deploys, run
`sudo /srv/agora/infra/runner/deploy.sh <commit>` on the runner Droplet with the
same commit, so both sides run the same code.

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

**A tool needs Agora to call an agent.** An admin creates an API token in
Settings, API tokens, and hands it over as a secret. The tool calls
`https://<app-domain>/api/v1/agents/<agent>/<version>/chat/completions` with
`Authorization: Bearer <token>`. Revoke tokens that are no longer needed.

**Running an audit.** Inquiry, Start an audit: pick an agent version and seeds.
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

**Measuring a behaviour.** Tally, then the behaviour, then "Generate scenarios".
Generation is one job: Bloom writes its understanding of the behaviour, then the
scenarios and a variation of each. It is stored once and never changes. Then
"Start a suite on this scenario set": choose the prompt versions and repetitions
(three by default). Each scenario at each repetition runs as its own job, and the
behaviour page charts the newest finished run per prompt version. Cite a rate
with its run's seed hash.

**Changing a behaviour.** Edit `seeds/bloom/<behaviour>/BEHAVIOR.md` and merge.
That is a new behaviour version with no scenarios: generate a new set, and rerun
suites on it. Earlier sets and their rates stay readable but are not compared
with the new ones. Never commit a `scenarios/` folder there; Agora refuses it.

**A generation failed.** Its error is on the behaviour page, under generation runs.
"Look like they contain real personal data" means the synthetic-data scan caught
something in what the model wrote; generate again, and if it repeats, tighten the
behaviour's `instructions.ideation`.

**Reading a run with Ethos.** Ethos, then "Read a run": choose a finished Inquiry,
Tally or rehearsal run. Each conversation is one job in which both judges read
every label family. The run page shows each label's share of replies with its
interval, each conversation's fit, and each judge's kept and dropped findings;
every count opens the quotes behind it. A finished Inquiry or Tally run links
straight to Ethos.

**A judge drops many findings.** The run page lists each judge's dropped findings
by reason. Many "quote not found" drops mean the judge paraphrases; "no valid
answer" means it did not use the answer tool. Both count against the judge and
are worth raising when choosing models.

**Running the scanners on other logs.** The Ethos scanners are ordinary Inspect
Scout scanners: `scout scan agora_worker/ethos/scanners.py -T <log folder> --model
<model>` runs them over any folder of Inspect logs, writing Scout's own results
locally. Agora does not import those results.

**Building the gold set.** An admin creates a gold set under Jury, Gold sets:
choose a finished run and how many transcripts (60 to start); the same seed draws
the same items. Each expert opens the set and labels transcripts one after another;
ratings stay private to each expert. Once two experts have labelled the items, an
admin computes agreement, which updates every label's trust badge. Compute again
after more labelling; earlier results are kept.

**Ethos disagreements.** Reviewers find them under Jury, Ethos disagreements. Each
verdict is stored beside the judges' findings.

**Exporting a run.** Record lists every run. Finished runs export a PDF report
that opens with the full provenance, scores (Inquiry, Tally) or findings (Ethos)
as CSV, and the provenance as JSON. Every export is in the audit log.

**Someone cannot sign in: "belongs to another sign-in identity".** Their email
already belongs to an account with a different identity-provider subject, for
example after they were re-created at the provider. Agora never relinks accounts
by email on its own. Find the `auth.refused` event in Settings, audit log, which
records the new issuer and subject; confirm with the person and the identity
provider's admins that the new identity is theirs; then move the account to it:

```sql
UPDATE "user" SET oidc_issuer = '<issuer>', oidc_subject = '<subject>'
WHERE email = '<email>';
```

**Reading a run with an open model.** On an Ethos run page, "Signals from an open
model" lists witness runs on the same source; authors start one by choosing a
reader. The jobs go to the `witness` queue and wait for the runner. The run page
sets each signal beside the Ethos label it tracks, and every count opens its
replies. The response view shows a signals pane for the newest witness run that
read the conversation, or the one in its `witness` link.

**Witness jobs stay queued.** Only the runner takes the `witness` queue. Check
it is up (`docker compose -f /srv/agora/infra/runner/compose.yaml ps` on the
Droplet) and its logs; see `infra/runner/README.md`.

**A witness sample failed.** The error is on the run page. "Changed after launch"
means `config/witness.yaml` changed since the run began: launch a new run.
"Reports version" means the reader's image reports a different version from the
reader's `version`: fix the image or the configuration, then launch again. Signals
that fail the checks are dropped and counted on the run page; the raw response is
in Spaces beside the run (`runs/<run>/samples/<n>-witness.json`).

**Adding a witness reader.** Add it to `config/witness.yaml`, with its image
pinned by digest and its `version` set to what the image reports. Pull the image
and put the weights under `/srv/models` on the runner, then deploy both sides.
Locally, `AGORA_WITNESS_FILE=config/witness.dev.yaml` gives the lexicon
reader, which needs no GPU.

**Turning on full thinking.** Only once Anthropic has granted the account access:
set `thinking: full` on the `target` role in `config/models.yaml` and merge. Runs
launched after that record the setting and send the beta header. Admins and
compliance read full thinking from a transcript page, under "Full thinking
(restricted)"; each reading is in the audit log as `transcript.full_thinking`.

**The audit log** is append-only in Postgres. Compliance and admins read it in
Settings, audit log.

## Model providers and retention

Every auditor, target and judge call sends content to a provider. Record each
provider's retention terms here before it is used, and use zero data retention
arrangements where available. Agora sends only synthetic content until an admin
approves an import.

| Provider | Used for | Retention terms | Zero data retention | Confirmed by, date |
| --- | --- | --- | --- | --- |
| Anthropic | Target, auditor, judge A, scanner, Bloom scenarios (`config/models.yaml`) | To confirm for our account | To confirm. Claude Fable 5.1 is not available under zero data retention | |
| OpenAI | Judge B on the Ethos panel (`openai/gpt-6.1-sol`) | To confirm for our account | To confirm | |

Witness readers run open-weight models on our own runner, with no network, so
transcripts they read do not leave our infrastructure.

## Milestone status

### Milestone 7: runner

Built: separate queues for work App Platform cannot host, with a test that every
task's queue has a worker; full thinking as an opt-in on Anthropic roles, stored
apart from summaries and readable only by admins and compliance, with each reading
audited; the open-model witness: reader configuration, the `agora.witness/1`
contract, a command runner and a development lexicon reader, signal checks in
code, witness runs on the `witness` queue with read-only signals, a comparison
with Ethos labels on the run page and in the PDF report, and a signals pane in the
response view; and the Droplet runner (image, compose file, cloud-init, deploy
script). Dish was assessed and left out for now; see docs/DECISIONS.md.

Verified: in the tests, a lexicon run over an Inquiry run beside its Ethos run, with
replies in the right cells, exact token offsets, the PDF section, and signals
read-only once the run finished; a reader changed after launch and a runner on
another version both failing on the first attempt with nothing stored; the
command runner speaking the contract, and failing clearly on a crash, bad output
or a timeout; every kind of bad signal dropped with its reason; full thinking
stored apart from the summary, readable by an admin, refused to a reviewer and
audited. In a browser, in light and dark: a witness run started from an Ethos run
page and read by the local worker, its comparison table, a count opened to its
replies, and the signals pane in the response view. The full-thinking card was
checked by the tests only: the development models cannot return full thinking.
The runner's image and Droplet setup are written but not yet built on a Droplet.

Waiting on: a GPU Droplet and the first production reader; answers to the open
questions in docs/DECISIONS.md, above all which open model and signals to use and
whether Dish is worth adding; Anthropic's decision on full thinking.

### Milestone 6: jury and record

Built: gold sets drawn from finished runs by a seeded sample; blind labelling of
every label on every reply; Krippendorff's alpha per label between experts and
between each judge and the experts' median, kept with its time; trust badges set
from the experts' alpha; Ethos disagreements in the review queue with verdicts on
each finding; PDF reports for every run kind that open with full provenance; a
Ethos findings CSV; the Record page for every run; and a clear refusal when an
email arrives from a different sign-in identity.

Verified: in the tests, two experts labelling six transcripts blind, agreement of
1.0 on a label they agreed on and trust set to trusted, a systematic disagreement
retired, judges' alphas against the experts, refusals for non-reviewers and for
ratings on the member's messages; an Ethos disagreement reviewed and leaving the
queue; PDF text carrying the run's config and seed hashes; the findings CSV
carrying provenance on every row; and the sign-in refusal with its audit event. In
a browser: a gold set created, labelled by two experts, agreement computed, the
disagreement queue, the Record page and a downloaded PDF.

Waiting on: expert reviewers to label the first 60-transcript gold set with real
models' transcripts; answers to the open questions in docs/DECISIONS.md.

### Milestone 5: ethos

Built: five Inspect Scout scanners, one per label family, asking for findings as
structured output; a judge panel from two model families (`judge_a` Claude Opus
5.5, `judge_b` OpenAI's gpt-6.1-sol) with a second development family locally;
Ethos runs over finished runs, one job per conversation; every quote checked in
code, with offsets, and failures dropped and counted per judge; per-reply medians,
disputes and fit against expected profiles; label shares with Wilson intervals;
the response view with family tints, profile strips, the findings pane, thinking
summaries in their own pane and the turn timeline; the run page, the compare view
and the label reference.

Verified: in the tests, a panel reading with scripted judges (four findings kept
with exact offsets, including one on a thinking summary; a paraphrase, a citation
of the member's message and an unanswered family dropped and counted; a disputed
label; medians, fit and intrusions as expected; findings read-only once the run
closed), Scout's own `scan_async` over a folder of Inspect logs, and a comparison
of two prompt versions. In a browser with the development judges: two Ethos runs
over 18-conversation Tally runs, the response view, the run page and the
compare view.

Waiting on: an OpenAI key and confirmation of judge B's model ID, price and
retention terms; answers to the open questions in docs/DECISIONS.md.

### Milestone 4: tally

Built: five behaviours in `seeds/bloom/` in petri_bloom 0.2.6's format; scenario
generation as a one-job run whose output is a write-once scenario set; suites of
one run per prompt version, with a job per scenario and repetition that runs
Bloom's own task with its auditor aimed at Agora's Petri target, so the agent's
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

### Milestone 3: inquiry

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
side-by-side prompt diffs; the rehearsal; API tokens and the OpenAI-compatible
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
