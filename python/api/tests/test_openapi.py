from collections import Counter

from bench_api.main import app


def test_operation_ids_are_unique() -> None:
    """The web client names functions after operation IDs; a clash silently drops one."""
    ids = [
        operation["operationId"]
        for path in app.openapi()["paths"].values()
        for operation in path.values()
    ]
    assert [name for name, count in Counter(ids).items() if count > 1] == []
