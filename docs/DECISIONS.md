# Decisions

Every design choice, and every place the brief and a library's current
documentation disagree. Current documentation wins; the entry says so. Newest
milestone first within each section.

## Milestone 4: measure

### Where the brief and current documentation differ

**Bloom itself has moved.** `safety-research/bloom` says it "has a new home" and
"will not receive updates"; its last commit is 7a18428 (2026-05-07) and its last
release v1.1.0. Its successor is Meridian Labs' `petri_bloom`, an implementation
of Bloom on Petri and Inspect, and this is the "Petri 3 Bloom integration" the
brief asks us to check first. Bench pins `petri-bloom==0.2.6` (the PyPI source
matches the repository's head apart from one comment), and CLAUDE.md's "pin
bloom" applies to it. The frozen repository had no Inspect dependency, wrote
Petri-style JSON rather than `.eval` logs, reached targets through LiteLLM with no
per-target base URL, and had its evaluator write a fresh system prompt for every
rollout.

**Behaviour folders use petri_bloom's format.** The brief asks for `seed.yaml`,
`behaviors.json` and `models.json` per behaviour, "as Bloom expects". petri_bloom
expects `BEHAVIOR.md` (YAML front matter and the definition) and an optional
`examples/` folder, and chooses models per call rather than per folder. Bench's
behaviours live in `seeds/bloom/<behaviour>/BEHAVIOR.md`; models come from the
`scenarios` role in `config/models.yaml`.

**Our prompt stays fixed without the OpenAI-compatible route.** petri_bloom's
`bloom_audit` has no target parameter, but its solver can be replaced. Bench keeps
Bloom's task (its dataset, judge with Bloom's instructions, viewer and metadata)
and swaps in Bloom's auditor, with the same tools and system message, aimed at
Bench's Petri target from Explore. The target keeps the agent's real prompt and
passes whatever the auditor stages as a `<scenario_context>` block. Every Measure
run records `route: petri_target`. The OpenAI-compatible endpoint stays available
as the brief's fallback route, unused.

**Bloom's auditor and ideation are told our setting.** Bloom's auditor prompt asks
the auditor to write the target's system prompt, and its ideation prompt asks for
"the system prompt to the target model" and encourages real company names. Each
behaviour's `instructions.ideation` and `instructions.evaluation` (which petri_bloom
appends to those prompts) say that the agent's prompt is fixed, that staged text
arrives as context, which synthetic records exist, that no real organisations or
people may appear, and that the target must never be asked to show its reasoning.

**Forced tool choice degrades on current Claude models.** petri_bloom's generation
forces each `submit_*` tool. Claude Opus 5.5 rejects forced tool choice; Inspect
0.3.282's Anthropic provider detects such models and sends `auto` with a warning,
and petri_bloom retries when a reply has no tool call. Petri's judge and Scout do
not force tools.

**No elicitation rate ships with petri_bloom.** Neither petri_bloom nor Petri
computes one, so Bench does (`bench_core.measure.rates`): the share of scored
rollouts with presence 7 or more out of 10, as the brief and Bloom's original code define
it. Bloom's original counted unparsed scores as 0; Bench counts rollouts the judge
did not score apart, shows how many there were, and leaves them out of the rate.

**The presence dimension is found by tag.** petri_bloom's ideation names the
presence dimension itself and tags it `behavior`; Bench requires exactly one such
dimension in a scenario set and records its name on the set and on every run.

**Variation lineage is not recorded.** petri_bloom writes `variation: <axis>` on a
variation but nothing linking it to its base scenario, so Bench shows each
variation's axis but not which base scenario it came from.

### Design choices

**Scenarios are generated in Bench and stored in Postgres, once.** Generation is a
run of kind `scenarios` with one sample job, so it shares Explore's lifecycle,
budget, cancel and status stream. petri_bloom runs in memory on the behaviour as
it is in git; the result (its Behavior, with understanding, scenarios and
dimensions) is written once as a `scenario_set` row, read-only after its run
closes, and each generated seed becomes a `scenario` row with source `bloom`.
Folders in git hold only the definitions; a `scenarios/` folder there is refused,
so a set always has a run, models and a hash behind it.

**A behaviour version is its folder's content.** Its seed hash is a hash over
`BEHAVIOR.md` and its examples. A behaviour row is created for each version on
first use and by `sync-registry`, and never edited.

**A suite is one run per prompt version on one scenario set.** Each run has one
sample job per scenario and repetition (three by default), recorded with the suite
id. Its seed hash covers the behaviour's seed hash and the scenario set's content
hash, so a rate cited with it names exactly the scenarios behind it. Before a
rollout starts, the job checks the prompt, tools, scenario set hash and the
scenario's text against what the run recorded.

**Spread is the range of repetition rates.** Each repetition (an Inspect epoch
run as its own job) gets its own rate. Pages show the pooled rate, each
repetition's rate, and their lowest-to-highest range; the API also returns the
sample standard deviation. Severity is shown as the mean presence score.

**Rates are compared only within a scenario set.** The behaviour page charts the
newest finished run per prompt version on the selected scenario set; other sets
and earlier runs are listed, never mixed into the chart.

**Measure transcripts share Explore's tables and reader.** Rollouts are indexed
into `transcript`, `message` and `score` (source `bloom_judge`), so Lens and
expert review read them like any other transcript. Presence scores of 7 or more
join the review queue under the same rule as Petri's dimensions. The reader shows
presence first and links back to the Measure run.

**Generated text is scanned for personal data.** Before a scenario set is stored,
everything the model wrote (understanding, scenarios, generated rubrics) goes
through the synthetic-data scan; a finding fails the generation. Petri's own
built-in rubrics are skipped, since they ship with an example address.

**The development model plays Bloom's generator.** Offered a `submit_*` tool it
returns two placeholder scenarios, a variation per axis and one presence
dimension, so generation and suites run locally without keys.

**Generation usage comes from Inspect's usage record.** petri_bloom calls models
outside an eval, so Bench resets and reads Inspect's per-task usage record
(`init_model_usage`, `model_usage`, internal functions in 0.3.282) around it.

**Chart colour.** The rate chart uses one series colour, `--color-chart-1`
(`#2a78d6` light, `#3987e5` dark), which passes the palette checks against both
surfaces; the site's accent blue reads as grey at chart scale.

### Open questions

1. **Which model generates scenarios?** The `scenarios` role uses Claude Opus 5.5
   at high effort. A different family from the target would keep generation and
   rollout independent; worth deciding with the judge question from Milestone 3.
2. **How many scenarios?** Each behaviour asks for 4 base scenarios with two
   variation axes, so about 12 scenarios and 36 rollouts per prompt version.
   Bloom's authors used 50 or more. Larger sets narrow the spread and cost more.
3. **Reviewing generated scenarios.** Sets are generated in Bench and read there.
   Should an expert approve a set before suites can use it?

## Milestone 3: explore

### Where the brief and current documentation differ

**Inspect runs one eval at a time per process.** `eval_async` refuses concurrent
calls in one process. The worker serialises audits behind a lock, so samples on
one worker run one after another; to run more at once, raise the worker's
`instance_count`. Other jobs (system checks, housekeeping) still run alongside.

**Petri cannot resume a sample.** Its auditor and target keep their state in
memory with no checkpoints, and Inspect's checkpointing needs an agent that
calls it, which Petri's does not. With one sample per job, a sample interrupted
by a deploy is re-queued by `retry_stalled_jobs` and re-run from the start. This
meets the brief's aim (a deploy never loses an audit) at sample granularity.

**A judge dimension directory replaces Petri's defaults.** To keep Petri's 38
built-in dimensions alongside our six, the runner passes Petri's names plus our
parsed rubrics, as Petri's docs describe.

**Highlights are text, not structure.** The judge's highlights, summary and
reasons are free text citing `[Mn]`; Petri resolves each cite to a message id in
`scanner_references`. Bench stores those references with each transcript and
maps them to message positions, so every cite links to its message. Cites into
branches the auditor rolled back keep their id but no position.

**Compaction needs tiktoken's encoding file.** Petri's auditor compaction counts
tokens with tiktoken, which downloads an encoding on first use. Production can
fetch it (cached in `TIKTOKEN_CACHE_DIR`); compaction is a recorded run option,
on by default.

### Design choices

**Our target, inside Petri.** `bench_worker.explore.target` follows Petri's own
target agent and TargetContext protocol. The auditor's system message becomes
the context block after our real prompt (its message id kept, so rollbacks
replay cleanly), the model sees our real tool schemas, and every tool call is
answered from fixtures inside the target. The auditor therefore runs with
`target_tools="none"`: it plays the member and sees only the agent's replies, as
a member would, while the judge sees the whole conversation including tool
calls. Letting the auditor simulate tool results instead is not offered yet.

**One sample per job.** Each seed at each repetition is its own job on the
`runs` queue, with a heartbeat on its `run_sample` row, one retry for failures,
and a check that the seed, prompt and tool profile still match what the run
recorded (a mismatch fails the sample without retrying). The run closes when no
sample is queued or running: succeeded if any sample succeeded (failures are
noted on the run), failed if all failed, stopped at budget if the budget ran out.

**Per-sample logs.** Each sample's `.eval` log is stored at
`runs/<run>/samples/<index>-e<epoch>.eval`, and indexed as one transcript: the
target's surviving conversation, the judge's summary and highlights, and one
score row per dimension (scale 1 to 10). The transcript page offers the log for
download, to open in Inspect View; hosting Inspect View inside Bench can follow.

**Token budgets.** Each sample is given the run's remaining tokens as Inspect's
`token_limit`; a sample that hits it is stored and marked stopped at budget, and
samples that start after the budget is spent stop without running.

**Reviewer care in Explore.** A transcript whose seed carries a content note
opens only for people who have opted in under Settings, preferences, and the
same applies to its log.

**The heatmap.** Rows are transcripts, columns are dimensions with ours first,
then a handful of Petri's most telling (concerning, needs attention,
disappointing, user over system prompt, sycophancy, over-refusal, admirable,
scenario realism), with a switch to show all. Cells are tinted by Petri's
palette for each dimension (red where higher is worse, green where higher is
better), and every cell links to the transcript and that score.

**The development model plays every Petri role.** Offered the auditor's tools it
runs a two-turn audit; offered the judge's tool it scores everything 1. That
proves the pipeline locally; its scores mean nothing.

### Open questions

1. **Auditor and judge models.** All three roles use Claude Opus 5.5 for now.
   Should the judge be a different model from the target? The rule that no
   family judges itself alone is written for Lens; it may be worth applying to
   Explore's judge too.
2. **Built-in seeds.** Petri ships 173 seeds; the brief suggests adding those
   matching our tags. Petri's tags (sycophancy, privacy violation, deception)
   suit some of our risks. Which should join our runs?

## Milestone 2: agents and adapter

### Where the brief and current documentation differ

**Thinking display must be requested.** Current Claude models default thinking
display to "omitted", which returns empty thinking text. Inspect 0.3.282 sends
`display: "summarized"` whenever a reasoning effort is set, so every role in
`config/models.yaml` sets `reasoning_effort`. With Anthropic's full-thinking beta
enabled, Inspect drops `display` and the API returns full thinking; the
`thinking_full` column is ready for that case. Source: Claude Platform docs,
"Thinking"; Inspect's Anthropic provider.

**Sampling settings are refused at load.** Current Claude models reject
non-default `temperature`, `top_p` and `top_k`. `config/models.yaml` refuses them,
and the OpenAI-compatible endpoint ignores them and lists them under
`bench.ignored_parameters`, so variation comes from repetition as the brief says.

**Effort defaults differ by model.** Claude Opus 5.5 defaults to `medium` effort,
one level below Claude Opus 5, so every role sets its effort explicitly.

**Inspect's synchronous log functions break a running event loop.** Bench calls
`write_eval_log_async` and `read_eval_log_async` from async code.

### Design choices

**Agents live in git.** `agents/<key>/` holds `agent.yaml`, `prompts/v<n>.md`
(front matter, then the prompt exactly as the agent receives it), `tools.json`
and `personas/`. The prompt's SHA-256 is taken over the text after the front
matter, trimmed. The pre-deploy job (`python -m bench_worker.cli migrate`) applies
migrations and then syncs the registry, replacing the brief's bare `alembic
upgrade head` so a deploy always knows what git says we test.

**What a run tested never changes.** A stored prompt version refuses edits, and
the sync refuses a version file whose text changed: a new prompt is a new
version file. Tool profiles and personas are identified by hash, so a changed
fixture or persona becomes a new row and old runs keep pointing at what they
used. Postgres triggers make these rows write-once.

**Fixtures answer tools deterministically.** Each tool in `tools.json` binds to a
fixture: a fixed response, a record looked up by one argument, or a match on
several arguments (identity checks). Fields can be withheld (`omit`), so a date
of birth used for verification is never returned by a lookup.

**The adapter sits on Inspect's model layer.** Petri, Bloom and Scout already use
Inspect, and it gives one interface across providers for the two-family judge
panel in milestone 5. In deployed mode the caller's system text (an auditor's
scenario, Bloom's generated system prompt, the playground's context box) goes
into a `<scenario_context>` block after our prompt, introduced by one neutral
line. Open mode passes the caller's prompt through and offers no tools.

**No refusal fallbacks.** Anthropic recommends server-side refusal fallbacks for
new code. Bench does not enable them: a fallback would let a different model
answer for the target or a judge, which would misattribute behaviour and break
provenance. A refusal is recorded as a refusal (`TurnEnd.refused`), which is
itself a finding.

**Conversations keep the full Inspect message.** Each message row stores its
visible text and thinking summary for querying, and the complete Inspect message
in `meta.inspect`. Thinking blocks are passed back unchanged with their
signatures, as current models require, and the transcript can be written out
exactly.

**Playground conversations are runs.** Starting one records the commit, config
and its hash, prompt SHA, tool profile hash and resolved model ID; a run refuses
to start without a commit. Spend is counted on every turn, a conversation that
reaches its token budget stops after the turn in progress, and finishing writes
the `.eval` log to Spaces and makes the run read-only. Only the person who
started a conversation (or an admin) can add to it. A transcript's `log_uri` is
empty until the log exists.

**Personas guide the person, not the agent.** In the playground a persona is a
script for the tester; the agent sees only what goes in the context box, as it
would see only what connected systems show.

**The OpenAI-compatible endpoint uses API tokens.** Admins issue and revoke
tokens in Settings; only their SHA-256 is stored and each is shown once. Tool
calls are answered from fixtures by default, with intermediate steps returned in
`bench.steps`; `bench_tool_results: "simulated"` returns the tool calls for the
caller to answer. Streaming is not supported yet.

**A development model.** `benchdev/scripted` is a deterministic Inspect provider
in `bench_core.agents.dev_model`. It calls a tool when it sees a claim or member
number and answers plainly with a short thinking summary, so the playground and
endpoint run end to end without provider keys. `config/models.dev.yaml` uses
it; docker-compose defaults to that file. Production refuses any role that names
a development model.

**Personal data scan.** `bench_core.synthetic` checks emails (reserved domains
only), phone numbers (ACMA's fictional ranges and public service lines only),
Medicare numbers (by check digit), long identifiers (they must carry a `TEST`
marker) and, for imports, given names. A test runs it over `agents/`, `seeds/`
and `config/` on every CI run. The import flow that uses it, with admin approval,
arrives with the first import, in milestone 5.

### Open questions

1. **Provider retention.** Confirm Anthropic's retention terms and zero data
   retention status for our account. Claude Fable 5.1 requires 30-day retention
   and is unavailable under zero data retention, so it should not be a role
   while synthetic-only is the rule.
2. **Context framing.** Is a neutral "context from connected systems" block the
   right stand-in for how production agents receive member data? If production
   uses tool results or a different wrapper, the adapter should match it.

## Milestone 1: foundations

### Where the brief and current documentation differ

**App Platform routes are now ingress rules.** The brief's spec sketch puts
`routes` on each service. The current app spec marks per-service `routes` as
deprecated in favour of a top-level `ingress.rules` block. `.do/app.yaml` uses
ingress rules: `/api` goes to `api` with the prefix preserved, everything else to
`web`. Source: DigitalOcean OpenAPI `app_service_spec.yml`.

**Spec validation needs a token unless it is schema-only.** `doctl apps spec
validate` calls DigitalOcean's API to check a spec fully. With `--schema-only` it
works offline and checks field names and types. CI runs the schema-only check;
the full check happens when the app is created or updated. Source: doctl
`commands/apps.go`.

**App Platform cannot send runtime logs to Spaces.** Its log forwarding supports
Papertrail, Datadog, Logtail and OpenSearch only. We read "logs go to a private
Spaces bucket" as Bench's own files: Inspect `.eval` logs and other artefacts,
written through the S3 API. Runtime logs stay in App Platform's log viewer until
we choose a forwarding destination (open question below).

**MinIO is retired as a community image.** MinIO stopped publishing community
images in October 2025 and archived its repository in 2026, so the last image no
longer receives security fixes. docker-compose runs SeaweedFS 4.48 as the local
S3 server; tests use moto's in-process S3 server. Both speak the same S3 API as
Spaces. Sources: [MinIO CE in 2026](https://glukhov.org/data-infrastructure/object-storage/minio-dead/),
[github.com/minio/minio](https://github.com/minio/minio).

**Procrastinate has no Alembic integration.** Its only migration integration is
for Django; otherwise "you are responsible for tracking which migrations you've
applied". We vendor Procrastinate 3.10.0's `schema.sql` into
`bench_core/migrations/sql/` and apply it in Alembic revision 0003, so the
pre-deploy job sets up the queue with everything else. To upgrade Procrastinate,
add an Alembic revision that applies each newer file from
`procrastinate/sql/migrations/` in order (`pre` files before the code deploy,
`post` files after). Source: Procrastinate docs, "Migrations".

**Stalled jobs are not retried automatically.** Procrastinate detects workers
that stop sending heartbeats but leaves their jobs in `doing`. The documented
answer is a periodic task, which we run every minute (`retry_stalled_jobs`).
Source: Procrastinate docs, "Retry stalled jobs".

**Requests through App Platform's edge end after 100 seconds.** Server-sent
event streams therefore close after 85 seconds and the browser reconnects; if a
stream fails before its first event, the page polls instead. The spec sets
`disable_edge_cache: true`, which DigitalOcean recommends for SSE.

**Next.js 16 renamed middleware to proxy.** `web/proxy.ts` uses the new name.
Turbopack is now the default for builds; `output: "standalone"` remains the
documented Docker route.

**TypeScript is pinned to 6.0.3, not 7.** TypeScript 7 is the native compiler and
ships no JavaScript API, which Next.js's build-time type check relies on.

**Authlib 1.9 prefers httpx2.** Authlib now warns when it falls back to `httpx`;
the API depends on `httpx2`. Tests still use `httpx` for the ASGI test client.

**The worker's run command matches the brief.** `procrastinate
--app=bench_worker.app.app worker` is correct for Procrastinate 3.10.

### Design choices

**Repository.** Bench lives in `andrewbupa/MindMap` rather than a new `bench`
repository; the brief's `bench/` root is this repository's root. The app spec
deploys from `andrewbupa/MindMap`, branch `main`.

**Region.** App Platform `syd`, with Postgres and Spaces in `syd1`: the only
Australian region DigitalOcean offers. Confirm this meets our data-residency
obligations before real data is ever considered.

**Sign-in lives in the API.** The API runs the OpenID Connect authorisation code
flow with PKCE through Authlib. After sign-in it creates a server-side session
and sets an HTTP-only, SameSite=Lax cookie; Postgres stores only the SHA-256 of
the token, so a database leak yields no usable sessions. Starlette's session
cookie is used only to carry OAuth state between login and callback, scoped to
`/api/auth` and valid for ten minutes. The web app forwards the cookie when its
server components call the API, so the API is the only place sessions are
checked.

**Roles.** A user may hold several of author, reviewer, compliance and admin;
admin passes every check. When `BENCH_OIDC_ROLE_MAP` maps identity-provider
groups to roles, the identity provider is the source of truth and roles follow
its groups at every sign-in. Without a map, admins grant roles in Settings. Emails
in `BENCH_BOOTSTRAP_ADMINS` are always admins, which is how the first admin
appears. Admins cannot remove their own admin role or deactivate themselves.

**Cross-site request protection.** Every write must carry `X-Bench-Request: 1`. A
cross-site form cannot set that header, and a cross-site script cannot send it
without a CORS preflight, which the API refuses. The OpenAI-compatible endpoint
in milestone 2 (`/api/v1/...`) uses bearer tokens and is exempt.

**The whole data model now.** Milestone 1 creates every table in the brief so
provenance and links are fixed early. Additions beyond the brief's table:
`run_sample` (each sample is its own resumable job), `user_session`,
`dropped_finding` (quotes that failed verification, counted against their
judge), `data_import` (the personal-data scan and admin approval), `system_check`,
`gold_item` and `gold_label` (the gold set's transcripts and each expert's
labels), `run.source_run_id` (a Lens run reads another run's transcripts),
`run.engine_versions`, `run.adapter_mode`, `run.route` (which Bloom route a run
used) and `annotation.channel` (visible answer or thinking summary). Agent
domains include `disputes`, which the brief uses for seeds.

**Read-only rules live in Postgres.** Triggers refuse any update or delete of a
finished run, and any insert, update or delete of its samples, transcripts,
messages, scores and annotations. The audit log refuses updates and deletes.
Code therefore writes a run's children first and marks it finished last. TRUNCATE
bypasses row triggers; the production database user should not own the tables
once we split owner and application roles (open question below).

**Database TLS.** App Platform provides `${db.CA_CERT}` as text. We write it to a
temporary file and connect with `sslmode=verify-full`, so the server's identity
is checked, not only the encryption.

**Commit provenance.** Components receive `${_self.COMMIT_HASH}` as
`BENCH_GIT_COMMIT`; `make dev` passes the local commit. A run will refuse to
launch without one.

**Worker restarts.** App Platform sends SIGTERM on deploy and kills after the
termination grace period, set to 120 seconds for the worker. Procrastinate's
graceful shutdown waits up to 100 seconds for running jobs. Anything killed
mid-job is re-queued within a minute by `retry_stalled_jobs`.

**Signed URLs.** The bucket is private. Evidence opens through a signed URL that
lasts five minutes, and each one issued is written to the audit log.
`BENCH_SPACES_PUBLIC_ENDPOINT` lets signed URLs name a host the browser can reach
when containers use another (locally, `localhost:8333` rather than `s3:8333`).

**Local development mirrors the ingress.** docker-compose puts Caddy in front at
`http://bench.localhost:3000`, routing `/api` to the API like App Platform's
ingress. Browsers resolve `*.localhost` to this machine, and inside the compose
network the same name points at Caddy, so the mock identity provider
(`navikt/mock-oauth2-server` 6.1.2) issues tokens with one issuer that both the
browser and the API agree on.

**Images.** One Python image serves the API, worker and migration job. uv is
installed with pip at a pinned version, which works on any builder. Both images
run as non-root users.

**Web client.** Generated by `@hey-api/openapi-ts` 0.99.0, pinned exactly because
it is pre-1.0 and makes breaking releases. Operation IDs are the API handler
names, so code reads `readMe()` rather than `readMeApiMeGet()`. CI fails if the
schema or the client drifts.

**Interface.** Plain components on `web/styles/tokens.css` until the first Claude
Design handoff. Placeholder tokens include a hue per Lens label family.

**Known advisory.** `npm audit` reports a denial-of-service advisory in `braces`,
reached only through `eslint-config-next`. It is a development dependency that
never ships in the web image; we will take the fix when Next publishes one.

### Open questions

1. **Identity provider.** Which provider (Microsoft Entra ID, Okta, other)? Do
   roles come from its groups (set `BENCH_OIDC_ROLE_MAP`) or from admins in Bench?
   Who are the first admins?
2. **Data residency.** Does Sydney meet our obligations for synthetic data now,
   and for de-identified production samples later?
3. **Domain.** A custom domain, or the default `ondigitalocean.app` address? The
   identity provider's redirect URI depends on it.
4. **Runtime logs.** Should App Platform forward runtime logs to one of its
   supported destinations, or are its own log views enough?
5. **Database roles.** Split a table-owning migration role from the application
   role, so the application cannot TRUNCATE or alter tables?
6. **Design brief.** `CLAUDE_DESIGN_BRIEF.md` is referenced by the brief but was
   not supplied.
