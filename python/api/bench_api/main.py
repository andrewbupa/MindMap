"""The Bench API. Every route lives under /api, which App Platform routes here unchanged."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.sessions import SessionMiddleware

from bench_api import auth
from bench_api.routes import audit_log, health, me, system, users
from bench_core import queue
from bench_core.config import get_settings

log = logging.getLogger("bench_api")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-bench-request"
# Requests that carry their own credentials rather than the session cookie.
CSRF_EXEMPT_PREFIXES = ("/api/v1/",)


def operation_id(route: APIRoute) -> str:
    """Name operations after their handler, so the web client reads ``readMe()``."""
    return route.name


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with queue.app.open_async():
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Bench API",
        version="0.1.0",
        description="Tests our AI agents three ways: Explore, Measure and Lens.",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
        generate_unique_id_function=operation_id,
    )

    @app.middleware("http")
    async def require_csrf_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Cookie-authenticated writes must carry a custom header, which a cross-site form
        cannot set and a cross-site script cannot send without a CORS preflight we refuse."""
        path = request.url.path
        if (
            request.method not in SAFE_METHODS
            and not path.startswith(CSRF_EXEMPT_PREFIXES)
            and request.headers.get(CSRF_HEADER) != "1"
        ):
            return JSONResponse(
                {"detail": "Missing X-Bench-Request header."},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return await call_next(request)

    # Holds only OAuth state, nonce and PKCE verifier between login and callback.
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret.get_secret_value(),
        session_cookie="bench_oauth",
        max_age=600,
        path="/api/auth",
        same_site="lax",
        https_only=settings.secure_cookies,
    )

    for router in (
        health.router,
        auth.router,
        me.router,
        users.router,
        audit_log.router,
        system.router,
    ):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
