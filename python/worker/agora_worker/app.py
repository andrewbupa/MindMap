"""The worker's Procrastinate app. Start it with:

    procrastinate --app=agora_worker.app.app worker

The app object is the one in ``agora_core.queue``, so the API defers onto the same
queue; importing the task modules here registers them.
"""

from __future__ import annotations

import logging

from agora_core.queue import app
from agora_worker.tasks import companion, explore, lens, maintenance, measure, system_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

__all__ = ["app", "companion", "explore", "lens", "maintenance", "measure", "system_check"]
