"""Version del motor y clave de reproduccion.

Un dataset publicado tiene que poder reproducirse: los mismos bytes de entrada,
la misma version de mapeo y la misma version del motor deben producir la misma
salida, o fallar diciendo por que. Eso exige dos cosas que este modulo da:

* **nombrar la version del motor sin tokens flotantes.** `latest` no nombra
  nada: manana apunta a otro binario y el mismo manifiesto produce otro
  resultado. El contrato de linaje los prohibe explicitamente;
* **una clave estable sobre las entradas.** `reproduction_key` es el sha256 del
  JSON canonico —claves ordenadas, separadores compactos, UTF-8— de todo lo que
  entra, **sin** los digests de salida. Incluir la salida haria que la clave
  cambiara con el resultado, que es justo lo contrario de lo que sirve.

Aqui no hay estado: la fila de `engine_release` la escribe la semilla, y
aprobarla es una decision humana que este codigo no toma.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Final

# Version del esquema canonico que este codigo sabe escribir. Cambia cuando
# cambia la forma de lo publicado, no cuando cambia el codigo que lo escribe.
CANONICAL_SCHEMA_VERSION: Final[str] = "0.1.0"

# La version del motor de extraccion y mapeo de P3. El numero es parte del
# nombre a proposito: sin el, dos ejecuciones distintas serian indistinguibles.
ENGINE_RELEASE_KEY: Final[str] = "fnc-p3-mapping-0.1.0"

# Lo que compone esta version. `component_kind` sale del contrato de linaje.
ENGINE_COMPONENTS: Final[tuple[dict[str, str], ...]] = (
    {"component_id": "csv-extractor", "component_kind": "parser",
     "version": "0.1.0", "digest": hashlib.sha256(b"csv-extractor:0.1.0").hexdigest()},
    {"component_id": "column-mapping", "component_kind": "rule_set",
     "version": "0.1.0", "digest": hashlib.sha256(b"column-mapping:0.1.0").hexdigest()},
)

# Tokens que no nombran una version. El contrato de linaje los lista uno a uno.
FLOATING_TOKENS: Final[frozenset[str]] = frozenset(
    {"latest", "main", "head", "stable", "current"})

# Campos que entran en la clave de reproduccion. `output_digests` queda fuera:
# la clave describe la entrada, no el resultado.
MANIFEST_INPUT_FIELDS: Final[tuple[str, ...]] = (
    "canonical_schema_version",
    "company_id",
    "deterministic_config",
    "engine_release_key",
    "input_artifact_sha256",
    "locale",
    "mapping_definition_digest",
    "mapping_version_id",
    "random_seed",
    "source_schema_digest",
    "timezone",
)


class ReleaseError(ValueError):
    """La version del motor no nombra nada reproducible."""


def validate_release_key(key: str) -> None:
    """Rechaza un identificador de version que no se pueda reproducir."""
    if not key or not (3 <= len(key) <= 120):
        raise ReleaseError("release key must be between 3 and 120 characters")
    if key.strip().lower() in FLOATING_TOKENS:
        raise ReleaseError(f"floating release token is not reproducible: {key}")


def canonical_json(payload: dict[str, Any]) -> str:
    """JSON canonico: claves ordenadas, separadores compactos, UTF-8.

    Dos procesos que serialicen el mismo manifiesto tienen que producir los
    mismos bytes; si no, la clave de reproduccion depende del serializador.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def reproduction_key(manifest: dict[str, Any]) -> str:
    """sha256 del JSON canonico de las entradas declaradas.

    Un campo ausente es un error, no un hueco: una clave calculada sobre menos
    entradas de las declaradas afirmaria una reproducibilidad que no se tiene.
    """
    missing = [field for field in MANIFEST_INPUT_FIELDS if field not in manifest]
    if missing:
        raise ReleaseError(f"manifest is missing required fields: {sorted(missing)}")
    validate_release_key(str(manifest["engine_release_key"]))
    subset = {field: manifest[field] for field in MANIFEST_INPUT_FIELDS}
    return hashlib.sha256(canonical_json(subset).encode("utf-8")).hexdigest()


def digest_of(value: Any) -> str:
    """Huella de un valor tipado, para un nodo de linaje.

    El grafo guarda la huella y jamas el valor: `raw_value_stored_in_node` es
    `false` en el contrato, y un grafo que copia importes se convierte en una
    segunda base de datos que nadie protege.
    """
    if isinstance(value, dict):
        material = canonical_json(value)
    elif isinstance(value, (list, tuple)):
        material = json.dumps(list(value), sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False)
    else:
        material = "" if value is None else str(value)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
