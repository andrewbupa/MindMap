# The Droplet runner: Agora's Python image with the Docker CLI, so jobs on the
# sandbox and witness queues can start containers on the host's daemon (Dish
# sandboxes, and the GPU images witness readers run). Build context is the
# repository root; deploy.sh builds python/Dockerfile first and passes it in.
ARG AGORA_IMAGE
FROM docker:29.9.2-cli AS docker-cli

FROM ${AGORA_IMAGE}

USER root
# Static binaries, so they run on the Debian base unchanged.
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins/docker-compose \
    /usr/local/libexec/docker/cli-plugins/docker-compose
USER agora

CMD ["procrastinate", "--app=agora_worker.app.app", "worker", "--queues", "sandbox,witness"]
