# Common tasks. Python commands run in the uv workspace under python/.
.PHONY: dev dev-down migrate lint test seed-demo openapi check-openapi spec

UV := cd python && uv run
SPEC_DOCTL ?= doctl

## Start everything locally at http://bench.localhost:3000 (Docker required).
dev:
	BENCH_GIT_COMMIT=$$(git rev-parse HEAD) docker compose up --build

dev-down:
	docker compose down

## Apply database migrations to BENCH_DATABASE_URL.
migrate:
	$(UV) alembic upgrade head

lint:
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) mypy core/bench_core api/bench_api worker/bench_worker
	cd web && npm run lint && npm run typecheck

test:
	$(UV) pytest

seed-demo:
	$(UV) python -m bench_worker.cli seed-demo

## Regenerate the web client from the API's OpenAPI schema.
openapi:
	$(UV) python -W ignore -m bench_api.export_openapi ../web/lib/api/openapi.json
	cd web && npm run openapi

## Fail if the committed client is out of date (used in CI).
check-openapi: openapi
	git diff --exit-code -- web/lib/api

## Check the App Platform spec's schema. Needs no DigitalOcean token.
spec:
	$(SPEC_DOCTL) apps spec validate --schema-only .do/app.yaml
