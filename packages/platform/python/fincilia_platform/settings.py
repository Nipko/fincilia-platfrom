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
import re
from typing import Literal

from pydantic import Field, PostgresDsn, ValidationInfo, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

GATED_CAPABILITIES = ("ai_gateway_enabled", "payments_enabled")

# Nombres que no nombran una version. El contrato de linaje los lista uno a uno.
FLOATING_TOKENS = frozenset({"latest", "main", "head", "stable", "current"})


class Settings(BaseSettings):
    """Ajustes del proceso. Todo llega por entorno; nada se adivina."""

    model_config = SettingsConfigDict(
        env_prefix="FINCILIA_",
        env_file=None,
        extra="forbid",
        frozen=True,
        case_sensitive=False,
    )

    env: Literal["local", "test", "pilot"] = Field(
        description="Pilot requiere una atestacion KMS; el nombre no autoriza datos.")
    service_name: str = Field(default="fincilia-api", min_length=3)
    log_level: Literal["debug", "info", "warning", "error"] = Field(default="info")
    build_revision: str = Field(
        default="development",
        description="SHA Git completo de la imagen o development en local.")
    release_id: str = Field(
        default="unreleased",
        description="Identificador inmutable del candidato; no implica aprobacion.")
    otel_endpoint: str = Field(
        default="disabled",
        description="`disabled` mientras no exista colector local.")
    secret_source: Literal["local_env", "aws_secrets_manager"] = Field(
        default="local_env",
        description="Procedencia de secretos; pilot nunca acepta local_env.")

    database_url: PostgresDsn = Field(
        description="DSN del rol runtime, nunca del propietario del esquema.")
    database_pool_min: int = Field(default=1, ge=0, le=32)
    database_pool_max: int = Field(default=8, ge=1, le=64)
    database_statement_timeout_ms: int = Field(default=15_000, ge=100, le=120_000)

    cache_url: str = Field(
        description="Valkey. Cache y progreso efimero; nunca autoridad financiera.")

    object_store_endpoint: str = Field(description="Endpoint S3 compatible o AWS S3.")
    object_region: str = Field(default="us-east-1", min_length=2)
    object_credentials_source: Literal["local_static", "aws_workload_identity"] = Field(
        default="local_static")
    object_access_key: str | None = Field(default=None, min_length=3)
    object_secret_key: str | None = Field(default=None, min_length=8)
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

    # Tokenizacion de identificadores de cuenta. **No** reutiliza la clave de
    # firma de tokens: un secreto que sirve para dos cosas tiene el radio de
    # explosion de las dos, y rotar una obligaria a rotar la otra.
    identifier_tokenization_key: str | None = Field(
        default=None,
        description="Clave HMAC para tokenizar identificadores de cuenta. "
                    "Obligatoria en el servicio que da de alta cuentas.")
    authorization_context_hmac_key: str | None = Field(
        default=None,
        description="Clave HMAC dedicada a referencias e idempotencia de "
                    "capabilities persistentes. Nunca llega al worker.")
    identifier_key_version: int = Field(
        default=1, ge=1, le=999,
        description="Version de la clave de tokenizacion. Rotarla sube este "
                    "numero; la identidad economica de la cuenta no cambia.")
    # Que version del motor ejecuta este proceso. Se nombra a proposito: elegir
    # «la mas reciente aprobada» seria una version flotante con otro nombre.
    engine_release_key: str = Field(
        default="fnc-p3-mapping-0.1.0", min_length=3, max_length=120,
        description="Clave de la version del motor con la que se publica.")

    real_data_enabled: bool = Field(default=False)
    ai_gateway_enabled: bool = Field(default=False)
    payments_enabled: bool = Field(default=False)
    registration_invite_required: bool = Field(
        default=False,
        description="Exige una invitacion de un uso en la beta cerrada sintetica.")
    oidc_enabled: bool = Field(default=False)
    oidc_issuer: str = Field(default="disabled")
    oidc_client_id: str = Field(default="disabled")
    oidc_token_endpoint: str = Field(default="disabled")
    oidc_userinfo_endpoint: str = Field(default="disabled")
    oidc_redirect_uri: str = Field(default="disabled")
    identity_binding_hmac_key: str | None = Field(default=None)
    identity_gate_attestation: str = Field(default="disabled")
    identity_gate_signature: str = Field(default="disabled")
    identity_gate_kms_key_id: str = Field(default="disabled")
    data_gate_attestation: str = Field(default="disabled")
    data_gate_signature: str = Field(default="disabled")
    data_gate_kms_key_id: str = Field(default="disabled")

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

    @field_validator("real_data_enabled")
    @classmethod
    def _real_data_needs_pilot_and_kms(cls, value: bool,
                                       info: ValidationInfo) -> bool:
        if value and (
            info.data.get("env") != "pilot"
            or info.data.get("secret_source") != "aws_secrets_manager"
        ):
            raise ValueError("real data requires pilot plus AWS Secrets Manager and a KMS gate")
        return value

    @field_validator("oidc_enabled")
    @classmethod
    def _oidc_needs_pilot(cls, value: bool, info: ValidationInfo) -> bool:
        if value and (
            info.data.get("env") != "pilot"
            or info.data.get("secret_source") != "aws_secrets_manager"
        ):
            raise ValueError("OIDC with personal data requires the gated pilot environment")
        return value

    @field_validator("identity_binding_hmac_key")
    @classmethod
    def _identity_binding_key(cls, value: str | None,
                              info: ValidationInfo) -> str | None:
        if info.data.get("oidc_enabled") and (value is None or len(value) < 32):
            raise ValueError("OIDC needs a dedicated identity binding HMAC key")
        if value and value in {
            info.data.get("auth_signing_key"),
            info.data.get("identifier_tokenization_key"),
            info.data.get("authorization_context_hmac_key"),
        }:
            raise ValueError("the identity binding key must not be reused")
        return value

    @model_validator(mode="after")
    def _environment_boundary(self) -> "Settings":
        """Comprueba campos relacionados despues de aplicar los defaults."""
        if self.object_credentials_source == "local_static":
            if not self.object_access_key or not self.object_secret_key:
                raise ValueError("local object storage needs explicit credentials")
        elif self.object_access_key or self.object_secret_key:
            raise ValueError(
                "AWS workload identity must not receive static object credentials")

        if self.env == "pilot":
            if self.secret_source != "aws_secrets_manager":
                raise ValueError("pilot secrets must come from AWS Secrets Manager")
            if self.object_credentials_source != "aws_workload_identity":
                raise ValueError("pilot object storage requires AWS workload identity")

        if self.real_data_enabled and any(value == "disabled" for value in (
                self.data_gate_attestation,
                self.data_gate_signature,
                self.data_gate_kms_key_id)):
            raise ValueError("real data needs a configured KMS gate attestation")

        if self.oidc_enabled:
            if self.registration_invite_required is not True:
                raise ValueError("pilot OIDC registration must remain invite-only")
            if not self.identity_binding_hmac_key or len(self.identity_binding_hmac_key) < 32:
                raise ValueError("OIDC needs a dedicated identity binding HMAC key")
            for name, value in (
                ("issuer", self.oidc_issuer),
                ("token endpoint", self.oidc_token_endpoint),
                ("userinfo endpoint", self.oidc_userinfo_endpoint),
                ("redirect URI", self.oidc_redirect_uri),
            ):
                if not value.startswith("https://"):
                    raise ValueError(f"OIDC {name} must be an exact HTTPS URL")
            if self.oidc_client_id == "disabled" or len(self.oidc_client_id) < 8:
                raise ValueError("OIDC client identifier is missing")
            if any(value == "disabled" for value in (
                    self.identity_gate_attestation,
                    self.identity_gate_signature,
                    self.identity_gate_kms_key_id)):
                raise ValueError("OIDC needs a configured DRG-00 KMS attestation")
        return self

    @field_validator("engine_release_key")
    @classmethod
    def _release_not_floating(cls, value: str) -> str:
        # `latest` no nombra nada: manana apunta a otro binario y el mismo
        # manifiesto produce otro resultado.
        if value.strip().lower() in FLOATING_TOKENS:
            raise ValueError(
                f"{value!r} is a floating token, not a reproducible release")
        return value

    @field_validator("build_revision")
    @classmethod
    def _build_revision_is_exact(cls, value: str) -> str:
        if value != "development" and not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValueError("build_revision must be a full Git SHA or development")
        return value

    @field_validator("release_id")
    @classmethod
    def _release_id_is_canonical(cls, value: str) -> str:
        if value != "unreleased" and not re.fullmatch(
                r"fnc-[a-z0-9][a-z0-9.-]{2,79}", value):
            raise ValueError("release_id must be immutable and canonical")
        return value

    @field_validator("identifier_tokenization_key")
    @classmethod
    def _tokenization_key_is_its_own(cls, value: str | None,
                                     info: ValidationInfo) -> str | None:
        if value is None:
            return None
        if len(value) < 32:
            raise ValueError("the tokenization key needs at least 32 characters")
        if value == info.data.get("auth_signing_key"):
            raise ValueError(
                "the tokenization key must not be the auth signing key: one secret "
                "for two purposes carries the blast radius of both")
        # Fail-closed fuera del entorno local. Hoy `env` solo admite `local` y
        # `test`, asi que esto no se puede alcanzar: es la trampa que salta el dia
        # que alguien anada `staging` sin haber decidido Vault o KMS.
        if (info.data.get("env") not in ("local", "test")
                and info.data.get("secret_source") != "aws_secrets_manager"):
            raise ValueError(
                "outside local and test this key must come from a key manager, "
                "not from an environment variable")
        return value

    @field_validator("authorization_context_hmac_key")
    @classmethod
    def _context_key_is_dedicated(cls, value: str | None,
                                  info: ValidationInfo) -> str | None:
        if value is None:
            return None
        if len(value) < 32:
            raise ValueError("the authorization context key needs at least 32 characters")
        if value in (info.data.get("auth_signing_key"),
                     info.data.get("identifier_tokenization_key")):
            raise ValueError(
                "the authorization context key must not be reused for signing "
                "or identifier tokenization")
        if (info.data.get("env") not in ("local", "test")
                and info.data.get("secret_source") != "aws_secrets_manager"):
            raise ValueError(
                "outside local and test this key must come from a key manager")
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
    # Dar de alta una cuenta exige tokenizar su identificador, y sin clave no se
    # puede: el proceso no arranca en vez de guardarlo en claro.
    identifier_tokenization_key: str = Field(
        min_length=32,
        description="Clave HMAC de tokenizacion. Sintetica en local; fuera de "
                    "local tiene que venir de un gestor de claves.")
    authorization_context_hmac_key: str = Field(
        min_length=32,
        description="Clave HMAC exclusiva de capabilities persistentes. "
                    "Sintetica en local; Vault/KMS fuera de local.")

    @model_validator(mode="after")
    def _real_api_requires_managed_identity(self) -> "ApiSettings":
        if self.real_data_enabled and not self.oidc_enabled:
            raise ValueError("real data API requires nominal managed identity")
        return self


class WorkerSettings(Settings):
    """Ajustes de un servicio que no emite ni valida tokens.

    Recibir la clave de firma seria ampliar su radio de explosion sin ninguna
    ganancia, asi que se rechaza explicitamente en vez de ignorarse.
    """

    @field_validator("identifier_tokenization_key")
    @classmethod
    def _no_tokenization_key(cls, value: str | None) -> None:
        # El worker extrae filas; no da de alta cuentas. Recibir la clave seria
        # ampliar su radio de explosion sin ninguna ganancia.
        if value:
            raise ValueError(
                "this service does not tokenise identifiers and must not receive "
                "the tokenization key")
        return None

    @field_validator("auth_signing_key")
    @classmethod
    def _no_signing_key(cls, value: str | None) -> None:
        if value:
            raise ValueError(
                "this service does not issue tokens and must not receive a signing key")
        return None

    @field_validator("authorization_context_hmac_key")
    @classmethod
    def _no_context_hmac_key(cls, value: str | None) -> None:
        if value:
            raise ValueError(
                "this service consumes capabilities but must not receive their HMAC key")
        return None


@functools.lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    return ApiSettings()  # type: ignore[call-arg]


@functools.lru_cache(maxsize=1)
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()  # type: ignore[call-arg]
