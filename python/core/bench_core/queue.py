"""The Procrastinate app shared by the API (which defers jobs) and the worker (which runs them).

Task code lives in ``bench_worker``; the API defers by task name, so it never
imports worker code.
"""

from __future__ import annotations

from typing import Any

import procrastinate
from procrastinate.app import WorkerOptions

from bench_core.config import get_settings
from bench_core.db import libpq_url

DEFAULT_QUEUE = "default"
RUNS_QUEUE = "runs"
# Work App Platform cannot host, taken by the Droplet runner (infra/runner): Docker
# sandboxes for Dish, and GPU work for the open-model companion.
SANDBOX_QUEUE = "sandbox"
COMPANION_QUEUE = "companion"
# What the App Platform worker listens to; the runner takes the rest.
PLATFORM_QUEUES = (DEFAULT_QUEUE, RUNS_QUEUE)
RUNNER_QUEUES = (SANDBOX_QUEUE, COMPANION_QUEUE)

# Every deploy restarts the worker. App Platform sends SIGTERM and waits for the
# component's termination grace period (120 s in .do/app.yaml) before killing it,
# so running jobs get 100 s to finish. Anything killed mid-flight is left "doing"
# with a stale heartbeat and is re-queued by the retry_stalled_jobs task.
WORKER_DEFAULTS: WorkerOptions = {
    # Audits spend most of their time waiting on model providers.
    "concurrency": 4,
    "shutdown_graceful_timeout": 100,
    "update_heartbeat_interval": 10,
    "stalled_worker_timeout": 30,
    "delete_jobs": "successful",
}


def build_app(import_paths: list[str] | None = None) -> procrastinate.App:
    return procrastinate.App(
        connector=procrastinate.PsycopgConnector(
            conninfo=libpq_url(get_settings()),
            kwargs={"application_name": "bench"},
            min_size=1,
            max_size=5,
        ),
        import_paths=import_paths or [],
        worker_defaults=WORKER_DEFAULTS,
    )


app = build_app()


async def defer(task_name: str, *, queue: str = DEFAULT_QUEUE, **kwargs: Any) -> int:
    """Defer a task by name and return its job ID."""
    job_id: int = await app.configure_task(name=task_name, queue=queue).defer_async(**kwargs)
    return job_id
