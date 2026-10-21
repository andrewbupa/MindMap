"""The worker's Procrastinate app. Start it with:

    procrastinate --app=bench_worker.app.app worker

The app object is the one in ``bench_core.queue``, so the API defers onto the same
queue; importing the task modules here registers them.
"""

from __future__ import annotations

import logging

from bench_core.queue import app
from bench_worker.tasks import explore, lens, maintenance, measure, system_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

__all__ = ["app", "explore", "lens", "maintenance", "measure", "system_check"]
