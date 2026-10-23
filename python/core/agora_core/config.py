"""Settings for every Agora process, read from the environment.

Every variable is prefixed ``AGORA_``. Locally they come from ``.env`` (ignored
by git); on App Platform they are component environment variables, with
secrets stored as ``type: SECRET``.
"""

from __future__ import annotations

import json
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Environment(StrEnum):
    local = "local"
    test = "test"
    production = "production"


class StorageKind(StrEnum):
    """Where Agora keeps files: Inspect logs and the judges' raw answers."""

    # A table in Postgres: no bucket to pay for, enough for a prototype.
    database = "database"
    # DigitalOcean Spaces, or any S3-compatible store.
    spaces = "spaces"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGORA_",
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.local
    git_commit: str = "unknown"
    public_url: str = "http://localhost:3000"
    # The zone months are counted in, for spend. Keep it the same as the web app's
    # NEXT_PUBLIC_AGORA_TIME_ZONE, which formats times on screen.
    time_zone: str = "Australia/Sydney"
    repo_root: Path = REPO_ROOT
    # Model roles; defaults to config/models.yaml under repo_root.
    models_file: Path | None = None
    # Open-model witness readers; config/witness.yaml when unset.
    witness_file: Path | None = None

    # Postgres. App Platform supplies ${db.DATABASE_URL} and ${db.CA_CERT}.
    database_url: str = "postgresql://agora:agora@localhost:5432/agora"
    database_ca_cert: SecretStr | None = None
    # Connections each process may hold. App Platform's dev database allows few, so
    # the spec lowers these.
    database_pool_size: int = 5
    database_max_overflow: int = 5
    queue_pool_size: int = 5

    # Files live in Postgres unless this says spaces.
    storage: StorageKind = StorageKind.database
    signed_url_seconds: int = 300

    # Spaces, or any S3-compatible store (moto in tests). Used only when storage is spaces.
    spaces_endpoint: str = "http://localhost:9000"
    # Where browsers reach storage, if not at spaces_endpoint. Used only for signed URLs.
    spaces_public_endpoint: str | None = None
    spaces_region: str = "syd1"
    spaces_bucket: str = "agora-logs"
    spaces_key: SecretStr = SecretStr("agora")
    spaces_secret: SecretStr = SecretStr("agora-secret")

    # OpenID Connect single sign-on.
    oidc_metadata_url: str = "http://localhost:8080/agora/.well-known/openid-configuration"
    oidc_client_id: str = "agora-local"
    oidc_client_secret: SecretStr = SecretStr("agora-local-secret")
    oidc_scopes: str = "openid profile email"
    oidc_groups_claim: str = "groups"
    # JSON object mapping an IdP group to a Agora role, e.g. {"agora-admins": "admin"}.
    oidc_role_map: Annotated[dict[str, str], NoDecode] = Field(default_factory=dict)
    # Comma-separated emails that receive the admin role on first sign-in.
    bootstrap_admins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    session_secret: SecretStr = SecretStr("local-only-session-secret-change-me")
    session_hours: int = 12

    @field_validator("oidc_role_map", mode="before")
    @classmethod
    def _parse_role_map(cls, value: Any) -> Any:
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value

    @field_validator("time_zone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown time zone {value!r}") from error
        return value

    @field_validator("bootstrap_admins", mode="before")
    @classmethod
    def _parse_admins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _refuse_local_secrets_in_production(self) -> Settings:
        if self.environment is Environment.production:
            if self.session_secret.get_secret_value().startswith("local-only"):
                raise ValueError("AGORA_SESSION_SECRET must be set in production")
            if not self.public_url.startswith("https://"):
                raise ValueError("AGORA_PUBLIC_URL must use https in production")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.public_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
