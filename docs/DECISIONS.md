# Decisions

Every design choice, and every place the brief and a library's current
documentation disagree. Current documentation wins; the entry says so. Newest
milestone first within each section.

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
