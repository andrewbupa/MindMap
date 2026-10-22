from __future__ import annotations

from fastapi import APIRouter

from agora_api.deps import ReaderUser
from agora_api.models_dep import Roles
from agora_api.schemas import ModelRoleOut, ModelRolesOut

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def model_roles(_: ReaderUser, roles: Roles) -> ModelRolesOut:
    """The exact model behind each role, from config/models.yaml."""
    return ModelRolesOut(
        roles=[
            ModelRoleOut(role=name, model=role.model, family=role.family, generate=role.generate)
            for name, role in roles.roles.items()
        ],
        budgets=roles.budgets,
        prices={
            model: {"input": float(price.input), "output": float(price.output)}
            for model, price in roles.prices.items()
        },
    )
