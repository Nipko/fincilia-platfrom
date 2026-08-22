"""Almacen de objetos tras una interfaz, con zonas explicitas.

Cuatro zonas y ninguna mas: `quarantine`, `raw`, `derived`, `exports`. No es
organizacion cosmetica; cada zona tiene reglas distintas sobre quien escribe y
que se puede borrar, y no tenerlas separadas acaba con un derivado sobreescrito
encima de la evidencia que lo justificaba.

Las claves son **direccionadas por contenido**: la ruta la fija el hash de los
bytes, no el nombre que traia el fichero. Dos consecuencias que importan: subir
lo mismo dos veces escribe lo mismo en el mismo sitio, y un nombre hostil
(`../../etc/passwd`) nunca llega a formar parte de una ruta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from .settings import Settings

ZONES = ("quarantine", "raw", "derived", "exports")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
UUID_SHAPE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
CONNECT_TIMEOUT_SECONDS = 5
READ_TIMEOUT_SECONDS = 30


class ObjectStoreError(RuntimeError):
    """El almacen no pudo atender. Nunca lleva credenciales en el mensaje."""


@dataclass(frozen=True)
class StoredObject:
    zone: str
    key: str
    version_id: str | None
    byte_size: int

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"zone": self.zone, "key": self.key,
                                      "byte_size": self.byte_size}
        if self.version_id:
            payload["version_id"] = self.version_id
        return payload


def object_key(company_id: str, content_sha256: str) -> str:
    """Ruta derivada del contenido, nunca del nombre que envio el cliente."""
    if not UUID_SHAPE.match(company_id):
        raise ObjectStoreError("a company identifier does not have the expected shape")
    if not SHA256.match(content_sha256):
        raise ObjectStoreError("a content digest does not have the expected shape")
    # Los dos primeros caracteres reparten las claves y evitan un prefijo unico
    # con millones de objetos debajo.
    return f"company/{company_id}/{content_sha256[:2]}/{content_sha256}"


class ObjectStore(Protocol):
    def put(self, zone: str, key: str, payload: bytes, *, content_type: str,
            metadata: dict[str, str] | None = None) -> StoredObject: ...

    def get(self, zone: str, key: str) -> bytes: ...

    def exists(self, zone: str, key: str) -> bool: ...


class S3ObjectStore:
    """Implementacion S3 compatible. En local apunta al MinIO del stack."""

    def __init__(self, settings: Settings) -> None:
        self._buckets = {
            "quarantine": settings.object_bucket_quarantine,
            "raw": settings.object_bucket_raw,
            "derived": settings.object_bucket_derived,
            "exports": settings.object_bucket_exports,
        }
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.object_store_endpoint,
            aws_access_key_id=settings.object_access_key,
            aws_secret_access_key=settings.object_secret_key,
            region_name=settings.object_region,
            config=BotoConfig(signature_version="s3v4",
                              s3={"addressing_style": "path"},
                              connect_timeout=CONNECT_TIMEOUT_SECONDS,
                              read_timeout=READ_TIMEOUT_SECONDS,
                              retries={"max_attempts": 2, "mode": "standard"}),
        )

    def bucket(self, zone: str) -> str:
        try:
            return self._buckets[zone]
        except KeyError:
            # Una zona desconocida no se crea sobre la marcha: seria un quinto
            # sitio donde buscar evidencia que nadie declaro.
            raise ObjectStoreError(f"{zone!r} is not one of the declared zones") from None

    def put(self, zone: str, key: str, payload: bytes, *, content_type: str,
            metadata: dict[str, str] | None = None) -> StoredObject:
        bucket = self.bucket(zone)
        try:
            response = self._client.put_object(
                Bucket=bucket, Key=key, Body=payload, ContentType=content_type,
                Metadata=metadata or {})
        except (BotoCoreError, ClientError) as error:
            raise ObjectStoreError(type(error).__name__) from error
        return StoredObject(zone, key, response.get("VersionId"), len(payload))

    def get(self, zone: str, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self.bucket(zone), Key=key)
            return response["Body"].read()
        except (BotoCoreError, ClientError) as error:
            raise ObjectStoreError(type(error).__name__) from error

    def exists(self, zone: str, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket(zone), Key=key)
            return True
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return False
            raise ObjectStoreError(type(error).__name__) from error
        except BotoCoreError as error:
            raise ObjectStoreError(type(error).__name__) from error


class InMemoryObjectStore:
    """Almacen en memoria para pruebas que no necesitan el stack levantado.

    No es un doble del comportamiento de S3: solo guarda y devuelve bytes. Las
    pruebas que dependen de versionado o de permisos usan el MinIO real.
    """

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put(self, zone: str, key: str, payload: bytes, *, content_type: str,
            metadata: dict[str, str] | None = None) -> StoredObject:
        if zone not in ZONES:
            raise ObjectStoreError(f"{zone!r} is not one of the declared zones")
        self.objects[(zone, key)] = payload
        return StoredObject(zone, key, None, len(payload))

    def get(self, zone: str, key: str) -> bytes:
        try:
            return self.objects[(zone, key)]
        except KeyError:
            raise ObjectStoreError("no such object") from None

    def exists(self, zone: str, key: str) -> bool:
        return (zone, key) in self.objects
