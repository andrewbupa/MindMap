# Runner

A Droplet that takes the work App Platform cannot host, from the same Postgres queue
and into the same Spaces bucket as the App Platform worker:

| Queue | Work | Status |
| --- | --- | --- |
| `witness` | An open-weight model reads a transcript and reports per-token signals | Ready; no production reader configured yet |
| `sandbox` | Petri Dish audits in Docker sandboxes | Waiting on the decisions in docs/DECISIONS.md, milestone 7 |

The App Platform worker listens on `default,runs` only (`.do/app.yaml`), so jobs on
these queues wait until a runner takes them. A test checks that every task's queue
is taken by one of the two.

## What runs where

- The runner container is Agora's Python image plus the Docker CLI (`Dockerfile`),
  running `procrastinate worker --queues sandbox,witness --concurrency 1`.
- It holds the host's Docker socket and starts sibling containers: a witness
  reader's GPU image, or a Dish sandbox. Socket access is root on the host, so the
  Droplet runs nothing else.
- A witness reader is a command in `config/witness.yaml`. The usual form is
  `docker run --rm -i --gpus all --network none -v /srv/models:/models:ro <image@digest>`:
  the image has the GPU and the weights, and no network.

## Set up a Droplet

1. Create a GPU Droplet from DigitalOcean's AI/ML-ready image, in the same region
   and VPC as the database, with `cloud-init.yaml` as user data. The image ships the
   NVIDIA driver and Container Toolkit ([recommended setup](https://docs.digitalocean.com/products/droplets/getting-started/recommended-gpu-setup/));
   cloud-init adds Docker if it is missing and points it at the NVIDIA runtime.
2. Add a cloud firewall: SSH from your administrators' addresses only, nothing else
   inbound. Outbound needs Postgres over the VPC, Spaces and the model providers
   over HTTPS, and the image registries at build time.
3. Add the Droplet to the database cluster's trusted sources.
4. Check the GPU from Docker: `docker run --rm --gpus all ubuntu nvidia-smi`.
5. Add a read-only deploy key for the repository, then clone it to `/srv/agora`.
6. Write `/etc/agora/runner.env` (mode 0600, owner root). Use the private
   (VPC) host in the database URL:

   ```sh
   AGORA_ENVIRONMENT=production
   AGORA_DATABASE_URL=postgresql://agora:...@private-....db.ondigitalocean.com:25060/agora?sslmode=require
   AGORA_DATABASE_CA_CERT=...
   AGORA_SPACES_ENDPOINT=https://syd1.digitaloceanspaces.com
   AGORA_SPACES_REGION=syd1
   AGORA_SPACES_BUCKET=...
   AGORA_SPACES_KEY=...
   AGORA_SPACES_SECRET=...
   # Only when Dish runs here: the provider keys for its model roles.
   ANTHROPIC_API_KEY=...
   ```

   Take the values from the App Platform worker's settings; the runner needs no
   sign-in or session settings.
7. Put model weights under `/srv/models` and pull or build each reader's image.
8. Start it: `sudo /srv/agora/infra/runner/deploy.sh`.

## Deploy a new commit

`sudo /srv/agora/infra/runner/deploy.sh <commit>` checks out the commit, builds the
Python and runner images tagged with it, and restarts the container. Deploy the
runner with the same commit as App Platform: runs record the commit that launched
them, and a sample refuses a reader whose configuration changed since launch.

Compose stops the container with SIGTERM and waits 120 seconds, as App Platform does.
A job cut off mid-sample is re-queued by the stalled-job task, like any other.

## The witness contract

The reader's command gets one JSON request on stdin and writes one JSON response on
stdout (`agora.witness/1`, defined in `agora_core/witness.py`):

- Request: the reader key, model, `version`, the signals to report, every message of
  the conversation in order (`id`, `index`, `role`, `text`), and `score`, the ids of
  the replies to report on. Thinking summaries are left out.
- Response: `contract`, `runner_version` (must equal the reader's `version`, or the
  sample fails), `tokens` read, and `signals`. Each signal names a message and a
  signal, gives `token_start`, and lists `tokens` as `{start, end, value}` with
  character offsets into the message text. Explanations (`nla` signals) go in
  `explanation`.

Agora checks every signal in code and drops any that name another message or
signal, whose offsets fall outside the text or overlap, or whose values are not
finite. The raw response is kept in Spaces beside the run.

## Check on it

- `docker compose -f /srv/agora/infra/runner/compose.yaml logs -f`
- Jobs waiting for a runner:
  `SELECT queue_name, status, count(*) FROM procrastinate_jobs WHERE queue_name IN ('sandbox', 'witness') GROUP BY 1, 2;`
