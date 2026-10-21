"""The Procrastinate app shared by the API (which defers jobs) and the worker (which runs them).

Task code lives in ``bench_worker``; the API defers by task name, so it never
imports worker code.
"""

from __future__ import annotations

from typing import Any

import procrastinate

from bench_core.config import get_settings
from bench_core.db import libpq_url

DEFAULT_QUEUE = "default"
RUNS_QUEUE = "runs"


def build_app(import_paths: list[str] | None = None) -> procrastinate.App:
    return procrastinate.App(
        connector=procrastinate.PsycopgConnector(
            conninfo=libpq_url(get_settings()),
            kwargs={"application_name": "bench"},
            min_size=1,
            max_size=5,
        ),
        import_paths=import_paths or [],
    )


app = build_app()


async def defer(task_name: str, *, queue: str = DEFAULT_QUEUE, **kwargs: Any) -> int:
    """Defer a task by name and return its job ID."""
    job_id: int = await app.configure_task(name=task_name, queue=queue).defer_async(**kwargs)
    return job_id
