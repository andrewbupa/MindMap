#!/usr/bin/env bash
# Build and start the runner at the commit checked out in /srv/agora, or at the
# commit given as the first argument. Run as root on the Droplet: the runner holds
# the Docker socket, and /etc/agora/runner.env is readable by root only.
set -euo pipefail

cd /srv/agora
if [ "${1:-}" != "" ]; then
  git fetch --quiet origin
  git checkout --quiet --detach "$1"
fi
AGORA_GIT_COMMIT="$(git rev-parse HEAD)"
DOCKER_GID="$(getent group docker | cut -d: -f3)"
export AGORA_GIT_COMMIT DOCKER_GID

docker build --quiet -f python/Dockerfile -t "agora-python:${AGORA_GIT_COMMIT}" .
docker build --quiet -f infra/runner/Dockerfile \
  --build-arg "AGORA_IMAGE=agora-python:${AGORA_GIT_COMMIT}" \
  -t "agora-runner:${AGORA_GIT_COMMIT}" .
docker compose -f infra/runner/compose.yaml up -d --remove-orphans
echo "runner started at ${AGORA_GIT_COMMIT}"
