"""Write the API's OpenAPI schema to a file, for generating the web client.

    uv run python -m bench_api.export_openapi ../web/lib/api/openapi.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from bench_api.main import app


def main() -> None:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
