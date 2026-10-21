"""Model roles from ``config/models.yaml``: which exact model plays each part.

Runs record the resolved model ID for every role. Aliases that can silently move to
a different model (``latest``, ``-preview``, wildcards) are refused at load time.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from bench_core.config import get_settings

MODEL_ID = re.compile(r"^[a-z0-9-]+/[A-Za-z0-9._:/-]+$")
ALIAS = re.compile(r"(latest|preview|\*|:default$)", re.IGNORECASE)


class ModelRolesError(ValueError):
    pass


class RoleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    generate: dict[str, Any] = Field(default_factory=dict)

    @field_validator("model")
    @classmethod
    def _exact(cls, value: str) -> str:
        if not MODEL_ID.match(value):
            raise ValueError(f"{value!r} is not in provider/model form")
        if ALIAS.search(value.split("/", 1)[1]):
            raise ValueError(f"{value!r} looks like an alias; name an exact model")
        return value

    @field_validator("generate")
    @classmethod
    def _no_sampling(cls, value: dict[str, Any]) -> dict[str, Any]:
        # Current Claude models reject non-default sampling; variation comes from repetition.
        banned = {"temperature", "top_p", "top_k"} & set(value)
        if banned:
            raise ValueError(f"do not set {', '.join(sorted(banned))}; repeat samples instead")
        return value

    @property
    def family(self) -> str:
        return model_family(self.model)


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: Decimal
    output: Decimal


class ModelRoles(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    roles: dict[str, RoleConfig]
    prices: dict[str, Price] = Field(default_factory=dict)
    budgets: dict[str, int] = Field(default_factory=dict)

    def role(self, name: str) -> RoleConfig:
        try:
            return self.roles[name]
        except KeyError:
            raise ModelRolesError(f"config/models.yaml has no {name!r} role") from None

    def resolved_ids(self, *names: str) -> dict[str, str]:
        return {name: self.role(name).model for name in names}

    def budget(self, kind: str, default: int = 1_000_000) -> int:
        return self.budgets.get(kind, default)

    def cost_usd(self, model: str, input_tokens: int, output_tokens: int) -> Decimal:
        """Estimated spend. Zero for models without a price, such as test models."""
        price = self.prices.get(model)
        if price is None:
            return Decimal(0)
        million = Decimal(1_000_000)
        return (price.input * input_tokens + price.output * output_tokens) / million


def model_family(model: str) -> str:
    """The family a model belongs to, for the rule that no family judges itself alone."""
    return model.split("/", 1)[0]


def load_model_roles(path: Path) -> ModelRoles:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ModelRoles.model_validate(data)
    except (OSError, yaml.YAMLError, ValidationError) as error:
        raise ModelRolesError(f"{path}: {error}") from error


@lru_cache
def get_model_roles() -> ModelRoles:
    settings = get_settings()
    return load_model_roles(settings.models_file or settings.repo_root / "config" / "models.yaml")
