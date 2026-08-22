"""Configuracion tipada y fail-closed de la API.

Los nombres de campo mapean **uno a uno** con las variables declaradas en
`docs/platform/runtime-config.json`, y `extra="forbid"` hace que una variable
`FINCILIA_*` no declarada impida arrancar. Es deliberado: una variable que existe
en el entorno y no en el contrato es configuracion que nadie reviso.

Tres decisiones que valen mas que su tamano:

1. **No hay valores por defecto para credenciales.** Si falta una, el proceso no
   arranca. Un default silencioso es como se acaba conectando un entorno a la base
   equivocada.
2. **El entorno se restringe a `local` y `test`.** `production` no es un valor
   posible en este binario: habilitarla es una decision humana con gate.
3. **Las capacidades con gate estan apagadas por contrato** y encender el flag
   hace fallar el arranque, no imprime una advertencia.
"""

from __future__ import annotations

import functools
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

GATED_CAPABILITIES = ("real_data_enabled", "ai_gateway_enabled", "payments_enabled")


class Settings(BaseSettings):
    """Ajustes del proceso. Todo llega por entorno; nada se adivina."""

    model_config = SettingsConfigDict(
        env_prefix="FINCILIA_",
        env_file=None,
        extra="forbid",
        frozen=True,
        case_sensitive=False,
    )

    env: Literal["local", "test"] = Field(
        description="Solo local o test. Produccion no es una variable de entorno.")
    service_name: str = Field(default="fincilia-api", min_length=3)
    log_level: Literal["debug", "info", "warning", "error"] = Field(default="info")
    otel_endpoint: str = Field(
        default="disabled",
        description="`disabled` mientras no exista colector local.")

    database_url: PostgresDsn = Field(
        description="DSN del rol runtime, nunca del propietario del esquema.")
    database_pool_min: int = Field(default=1, ge=0, le=32)
    database_pool_max: int = Field(default=8, ge=1, le=64)
    database_statement_timeout_ms: int = Field(default=15_000, ge=100, le=120_000)

    cache_url: str = Field(
        description="Valkey. Cache y progreso efimero; nunca autoridad financiera.")

    object_store_endpoint: str = Field(description="Endpoint S3 compatible local.")
    object_region: str = Field(default="us-east-1", min_length=2)
    object_access_key: str = Field(min_length=3)
    object_secret_key: str = Field(min_length=8)
    object_bucket_quarantine: str = Field(default="fincilia-quarantine", min_length=3)
    object_bucket_raw: str = Field(default="fincilia-raw", min_length=3)
    object_bucket_derived: str = Field(default="fincilia-derived", min_length=3)
    object_bucket_exports: str = Field(default="fincilia-exports", min_length=3)

    auth_issuer: str = Field(default="fincilia-local", min_length=3)
    auth_audience: str = Field(default="fincilia-api", min_length=3)
    auth_signing_key: str | None = Field(
        default=None,
        description="Clave local de firma de tokens de vida corta. Opcional en la "
                    "base y obligatoria solo en el servicio que emite tokens.")
    auth_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)

    real_data_enabled: bool = Field(default=False)
    ai_gateway_enabled: bool = Field(default=False)
    payments_enabled: bool = Field(default=False)

    @field_validator("cache_url")
    @classmethod
    def _cache_scheme(cls, value: str) -> str:
        if not value.startswith(("redis://", "valkey://", "rediss://")):
            raise ValueError("cache_url must be a redis/valkey URL")
        return value

    @field_validator("object_store_endpoint")
    @classmethod
    def _object_scheme(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("object_store_endpoint must be an http(s) URL")
        return value

    @field_validator("database_pool_max")
    @classmethod
    def _pool_bounds(cls, value: int, info: ValidationInfo) -> int:
        minimum = info.data.get("database_pool_min", 0)
        if value < minimum:
            raise ValueError("database_pool_max must not be below database_pool_min")
        return value

    @field_validator(*GATED_CAPABILITIES)
    @classmethod
    def _gated(cls, value: bool, info: ValidationInfo) -> bool:
        if value:
            raise ValueError(
                f"{info.field_name} is gated: enabling it needs a human-approved gate "
                "(DRG-00, DRG-01 or L-02), not an environment variable")
        return value

    @property
    def buckets(self) -> tuple[str, ...]:
        return (self.object_bucket_quarantine, self.object_bucket_raw,
                self.object_bucket_derived, self.object_bucket_exports)


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Se resuelve una vez por proceso. Un fallo aqui impide arrancar."""
    return Settings()  # type: ignore[call-arg]


class ApiSettings(Settings):
    """Ajustes del servicio que **emite** tokens.

    Solo aqui la clave de firma es obligatoria. Sacarla de la clase base evita que
    servicios que nunca firman nada la reciban igualmente: un secreto que un
    proceso no usa sigue estando en su entorno, en sus volcados y en sus logs si
    alguien se descuida.
    """

    auth_signing_key: str = Field(
        min_length=32,
        description="Clave local de firma. No es un secreto de produccion y no se "
                    "reutiliza fuera del stack local.")


class WorkerSettings(Settings):
    """Ajustes de un servicio que no emite ni valida tokens.

    Recibir la clave de firma seria ampliar su radio de explosion sin ninguna
    ganancia, asi que se rechaza explicitamente en vez de ignorarse.
    """

    @field_validator("auth_signing_key")
    @classmethod
    def _no_signing_key(cls, value: str | None) -> None:
        if value:
            raise ValueError(
                "this service does not issue tokens and must not receive a signing key")
        return None


@functools.lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    return ApiSettings()  # type: ignore[call-arg]


@functools.lru_cache(maxsize=1)
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
