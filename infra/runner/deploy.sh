#!/usr/bin/env bash
# Build and start the runner at the commit checked out in /srv/bench, or at the
# commit given as the first argument. Run as root on the Droplet: the runner holds
# the Docker socket, and /etc/bench/runner.env is readable by root only.
set -euo pipefail

cd /srv/bench
if [ "${1:-}" != "" ]; then
  git fetch --quiet origin
  git checkout --quiet --detach "$1"
fi
BENCH_GIT_COMMIT="$(git rev-parse HEAD)"
DOCKER_GID="$(getent group docker | cut -d: -f3)"
export BENCH_GIT_COMMIT DOCKER_GID

docker build --quiet -f python/Dockerfile -t "bench-python:${BENCH_GIT_COMMIT}" .
docker build --quiet -f infra/runner/Dockerfile \
  --build-arg "BENCH_IMAGE=bench-python:${BENCH_GIT_COMMIT}" \
  -t "bench-runner:${BENCH_GIT_COMMIT}" .
docker compose -f infra/runner/compose.yaml up -d --remove-orphans
echo "runner started at ${BENCH_GIT_COMMIT}"
