"""Dependencias externas de la API y su diagnostico.

Cada dependencia expone `probe()`, que **nunca lanza**: devuelve un estado. Un
healthcheck que se cae con una excepcion no informa de nada, y el orquestador solo
ve un 500 sin decirte cual de las tres piezas fallo.

Ninguna sonda escribe. `ready` responde una pregunta de lectura sobre si el
proceso puede atender, no ejecuta trabajo.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
import psycopg
import valkey
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from fincilia_platform.settings import Settings

PROBE_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class ProbeResult:
    name: str
    status: str
    detail: str = ""
    latency_ms: int | None = None

    @property
    def healthy(self) -> bool:
        return self.status == "up"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": self.name, "status": self.status}
        if self.detail:
            payload["detail"] = self.detail
        if self.latency_ms is not None:
            payload["latency_ms"] = self.latency_ms
        return payload


class Probe(Protocol):
    name: str

    def probe(self) -> ProbeResult: ...


def _timed(name: str, action) -> ProbeResult:
    started = time.perf_counter()
    try:
        detail = action() or ""
    except Exception as error:  # noqa: BLE001 - una sonda nunca propaga
        return ProbeResult(name, "down", _safe_reason(error))
    elapsed = int((time.perf_counter() - started) * 1000)
    return ProbeResult(name, "up", detail, elapsed)


def _safe_reason(error: Exception) -> str:
    """El motivo no lleva DSN, claves ni rutas: un healthcheck es publico."""
    return type(error).__name__


class DatabaseProbe:
    name = "postgresql"

    def __init__(self, settings: Settings) -> None:
        self._dsn = str(settings.database_url)
        self._timeout = int(PROBE_TIMEOUT_SECONDS)

    def probe(self) -> ProbeResult:
        def action() -> str:
            with psycopg.connect(self._dsn, connect_timeout=self._timeout) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_user, current_setting('server_version')")
                    row = cursor.fetchone()
            return f"{row[0]}@{row[1]}" if row else ""
        return _timed(self.name, action)


class SchemaProbe:
    """Cabeza de migracion aplicada.

    Sin esta sonda, el stack arranca «sano» contra una base vacia y el primer
    fallo llega en la primera consulta de negocio, con un error de tabla
    inexistente que no dice que faltaba migrar. Aqui la respuesta es explicita:
    `ready` da 503 y el cuerpo nombra el problema.

    Solo lee `schema_history`, que no lleva RLS ni datos de negocio.
    """

    name = "schema"

    def __init__(self, settings: Settings, *, expected_head: str | None = None) -> None:
        self._dsn = str(settings.database_url)
        self._timeout = int(PROBE_TIMEOUT_SECONDS)
        self._expected = expected_head

    def probe(self) -> ProbeResult:
        started = time.perf_counter()
        try:
            with psycopg.connect(self._dsn, connect_timeout=self._timeout) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT max(version) FROM fincilia.schema_history "
                        "WHERE status = 'applied'")
                    row = cursor.fetchone()
        except psycopg.errors.UndefinedTable:
            return ProbeResult(self.name, "down", "no schema history: never migrated")
        except Exception as error:  # noqa: BLE001 - una sonda nunca propaga
            return ProbeResult(self.name, "down", _safe_reason(error))
        head = row[0] if row else None
        elapsed = int((time.perf_counter() - started) * 1000)
        if head is None:
            return ProbeResult(self.name, "down", "schema history is empty", elapsed)
        if self._expected is not None and head != self._expected:
            # Una cabeza distinta de la esperada no es un aviso: la imagen y la
            # base no son la misma version del producto.
            return ProbeResult(self.name, "down",
                               f"head {head}, image expects {self._expected}", elapsed)
        return ProbeResult(self.name, "up", f"head {head}", elapsed)


class CacheProbe:
    name = "valkey"

    def __init__(self, settings: Settings) -> None:
        self._url = settings.cache_url

    def probe(self) -> ProbeResult:
        def action() -> str:
            client = valkey.Valkey.from_url(
                self._url, socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
                socket_timeout=PROBE_TIMEOUT_SECONDS)
            try:
                client.ping()
                return "pong"
            finally:
                client.close()
        return _timed(self.name, action)


class ObjectStoreProbe:
    name = "object_storage"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def client(self):
        settings = self._settings
        return boto3.client(
            "s3",
            endpoint_url=settings.object_store_endpoint,
            region_name=settings.object_region,
            aws_access_key_id=settings.object_access_key,
            aws_secret_access_key=settings.object_secret_key,
            config=BotoConfig(signature_version="s3v4",
                              connect_timeout=int(PROBE_TIMEOUT_SECONDS),
                              read_timeout=int(PROBE_TIMEOUT_SECONDS),
                              retries={"max_attempts": 1}),
        )

    def probe(self) -> ProbeResult:
        def action() -> str:
            client = self.client()
            missing: list[str] = []
            for bucket in self._settings.buckets:
                try:
                    client.head_bucket(Bucket=bucket)
                except (ClientError, BotoCoreError):
                    missing.append(bucket)
            if missing:
                # Se nombran los buckets porque son configuracion declarada, no
                # un secreto: sin esto el diagnostico no es accionable.
                raise RuntimeError(f"missing buckets: {sorted(missing)}")
            return f"{len(self._settings.buckets)} buckets"
        result = _timed(self.name, action)
        if result.status == "down" and result.detail == "RuntimeError":
            return ProbeResult(self.name, "down", "one or more declared buckets are absent")
        return result


def build_probes(settings: Settings, *,
                 expected_head: str | None = None) -> tuple[Probe, ...]:
    return (DatabaseProbe(settings), SchemaProbe(settings, expected_head=expected_head),
            CacheProbe(settings), ObjectStoreProbe(settings))


def probe_all(settings: Settings) -> tuple[ProbeResult, ...]:
    """Sondea las tres dependencias y devuelve resultados, nunca excepciones."""
    return tuple(probe.probe() for probe in build_probes(settings))


def ensure_buckets(settings: Settings) -> list[str]:
    """Crea las cuatro zonas de evidencia si faltan. Idempotente.

    Vive en el arranque del servicio y no en un contenedor aparte porque un
    contenedor de un solo uso hace que `docker compose up --wait` tenga que
    distinguir "salio con 0 porque termino" de "se cayo", y esa ambiguedad se paga
    cada vez que alguien levanta el stack.

    En un despliegue real esto es trabajo de infraestructura y el servicio recibe
    credenciales sin permiso de creacion. Aqui se hace en el arranque **solo**
    cuando el entorno es `local`, y quien llama debe comprobarlo.
    """
    store = ObjectStoreProbe(settings)
    client = store.client()
    created: list[str] = []
    for bucket in settings.buckets:
        try:
            client.head_bucket(Bucket=bucket)
        except (ClientError, BotoCoreError):
            client.create_bucket(Bucket=bucket)
            created.append(bucket)
    # `raw` es inmutable por contrato: el versionado impide que una sobreescritura
    # silenciosa cambie la evidencia que sostiene un cierre.
    client.put_bucket_versioning(
        Bucket=settings.object_bucket_raw,
        VersioningConfiguration={"Status": "Enabled"})
    return sorted(created)
