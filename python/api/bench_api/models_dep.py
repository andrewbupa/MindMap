"""Model construction, behind a dependency so tests can supply a scripted model."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from inspect_ai.model import Model, get_model

from bench_core.model_roles import ModelRoles, get_model_roles

ModelFactory = Callable[[str], Model]


def model_factory() -> ModelFactory:
    def build(model_id: str) -> Model:
        try:
            return get_model(model_id)
        except Exception as error:  # a provider without credentials raises at construction
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"The model provider for {model_id} is not configured: {error}",
            ) from error

    return build


Models = Annotated[ModelFactory, Depends(model_factory)]
Roles = Annotated[ModelRoles, Depends(get_model_roles)]
