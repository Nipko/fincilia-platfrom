"""Mapeo, validacion y publicacion de un dataset canonico.

Aqui vive la parte del producto que convierte filas de un fichero en hechos
economicos, y la que decide cuando eso puede publicarse. Tres reglas la
gobiernan, y ninguna se deja a la buena voluntad de quien llame:

* **lo ambiguo bloquea.** Si el perfilador no pudo decidir entre dos lecturas de
  una fecha o de un decimal, publicar seria elegir por la persona. Se bloquea
  hasta que alguien deja escrita su decision y por que;
* **quien prepara no publica.** La comprobacion esta ademas en un CHECK de la
  base, asi que no hay ruta —script, consola, error de programacion— que la
  esquive;
* **publicar no sobrescribe.** Repetir la publicacion de la misma terna no
  duplica nada, y reprocesar crea otra version que convive con la anterior.

Nada de esto concilia, empareja ni cierra: eso es de otra fase, y mezclarlo
haria que un error de mapeo se propagara a un cierre contable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import psycopg

from fincilia_contracts.mapping import (
    CANONICAL_FIELDS,
    ColumnMapping,
    MappingError,
    apply_row,
    validate_mapping,
)
from fincilia_contracts.release import (
    CANONICAL_SCHEMA_VERSION,
    ENGINE_RELEASE_KEY,
    digest_of,
    reproduction_key,
)

logger = logging.getLogger("fincilia.api.datasets")

# Techo de una publicacion. La extraccion admite mucho mas, pero cada campo
# publicado escribe nodos y aristas de linaje, y un dataset que no cabe se dice
# en vez de tragarselo a medias.
MAX_DATASET_ROWS = 10_000

# Cuantas filas devuelve como mucho una vista previa. La vista previa **si**
# lleva valores, y por eso pagina siempre: devolver el fichero entero por una
# peticion seria descargar la evidencia con otro nombre.
MAX_PREVIEW_LIMIT = 200
DEFAULT_PREVIEW_LIMIT = 50

# Que transformacion produjo cada campo canonico. `derived_from` exige nombrarla:
# sin eso el grafo diria «esto tiene algo que ver con aquello».
TRANSFORMS = {
    "occurred_on": "parse_date",
    "description": "verbatim",
    "reference": "normalise_reference",
    "amount": "normalise_amount",
    "direction": "resolve_direction",
    "currency": "declared_currency",
}

# Que esta eligiendo la persona cuando resuelve una columna ambigua. Se deriva
# del tipo que el perfilador no supo decidir, no de un cajon generico: quien
# resuelve un `13/02` frente a un `02/13` esta eligiendo un convenio de fecha, y
# el rastro tiene que decir eso y no «rol de columna».
AMBIGUITY_KINDS = {
    "ambiguous_date": "date_format",
    "ambiguous_numeric": "decimal_format",
}

# Y con que convenio del mapeo tiene que coincidir la eleccion. Una decision que
# dice `dmy` sobre un mapeo que declara `mdy` no resuelve nada: deja escrito que
# la persona quiso una cosa y el sistema hace otra.
DECLARED_BY_KIND = {
    "date_format": lambda mapping: mapping.date_format,
    "decimal_format": lambda mapping: mapping.decimal_format,
}


class PreparationError(Exception):
    """El dataset no se puede preparar, y el motivo es del cliente."""

    def __init__(self, code: str, detail: str,
                 blockers: list[dict[str, str]] | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.blockers = blockers or []


@dataclass(frozen=True)
class Preparation:
    dataset_version_id: str
    state: str
    movement_count: int
    rejected_count: int
    record_count: int
    reused: bool
    rejections: tuple[dict[str, Any], ...]


# --------------------------------------------------------------------------- #
# Lectura de lo extraido
# --------------------------------------------------------------------------- #

def latest_run(connection: psycopg.Connection, artifact_id: str,
               kind: str) -> dict[str, Any] | None:
    """La ultima ejecucion terminada bien de un tipo, con su resultado."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT run_id, result, finished_at FROM fincilia.processing_run "
            "WHERE artifact_id = %s AND kind = %s AND status = 'succeeded' "
            "ORDER BY finished_at DESC LIMIT 1", (artifact_id, kind))
        row = cursor.fetchone()
    if row is None:
        return None
    return {"run_id": str(row[0]), "result": row[1] or {},
            "finished_at": row[2].isoformat()}


def count_records(connection: psycopg.Connection, run_id: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM fincilia.raw_record "
                       "WHERE processing_run_id = %s", (run_id,))
        return int(cursor.fetchone()[0])


def effective_limit(limit: int) -> int:
    """El limite que de verdad se aplica. La vista previa siempre pagina."""
    try:
        return max(1, min(int(limit), MAX_PREVIEW_LIMIT))
    except (TypeError, ValueError):
        return DEFAULT_PREVIEW_LIMIT


def preview_records(connection: psycopg.Connection, run_id: str, *,
                    offset: int = 0,
                    limit: int = DEFAULT_PREVIEW_LIMIT) -> list[dict[str, Any]]:
    """Una pagina de registros con sus valores y su coordenada.

    Es la unica lectura del producto que devuelve el contenido del fichero, y por
    eso va por su propio endpoint, con permiso mas estricto que el perfil
    estadistico, y **no se registra en el evento de auditoria ni en las metricas**:
    el rastro dice quien miro y cuantas filas, nunca que ponia en ellas.
    """
    limit = effective_limit(limit)
    offset = max(0, int(offset))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT record_ordinal, raw_values, origin_locator "
            "FROM fincilia.raw_record WHERE processing_run_id = %s "
            "ORDER BY record_ordinal LIMIT %s OFFSET %s", (run_id, limit, offset))
        return [{"record_ordinal": ordinal, "values": values, "locator": locator}
                for ordinal, values, locator in cursor]


# --------------------------------------------------------------------------- #
# Mapeo
# --------------------------------------------------------------------------- #

def mapping_from_definition(definition: dict[str, Any]) -> ColumnMapping:
    """Construye el mapeo del dominio a partir de lo guardado.

    Un campo que no es canonico se rechaza aqui y no mas adelante: dejarlo pasar
    lo convertiria en una columna fantasma que nadie vuelve a mirar.
    """
    columns = definition.get("columns") or {}
    if not isinstance(columns, dict):
        raise PreparationError("mapping-invalid", "columns must be an object")
    unknown = sorted(set(columns) - set(CANONICAL_FIELDS))
    if unknown:
        raise PreparationError("mapping-invalid",
                               f"not canonical fields: {', '.join(unknown)}")
    try:
        return ColumnMapping(
            columns={name: int(index) for name, index in columns.items()},
            date_format=str(definition.get("date_format", "iso")),
            decimal_format=str(definition.get("decimal_format", "dot")),
            currency=str(definition.get("currency", "")),
            direction_mode=str(definition.get("direction_mode", "signed_amount")),
            header_row=int(definition.get("header_row", 1)),
            first_data_row=int(definition.get("first_data_row", 2)))
    except (TypeError, ValueError) as error:
        raise PreparationError("mapping-invalid", str(error)) from error


def definition_digest(definition: dict[str, Any]) -> str:
    return digest_of(definition)


def schema_digest(profile: dict[str, Any]) -> str:
    """Huella de la forma del fichero: cuantas columnas y como se llaman.

    Si esto cambia, los indices del mapeo apuntan a otras columnas sin que nada
    falle, que es exactamente el fallo que nadie ve.
    """
    headers = [str(column.get("header", ""))
               for column in (profile.get("columns") or [])]
    return digest_of({"column_count": profile.get("column_count"),
                      "headers": headers})


def create_mapping(connection: psycopg.Connection, *, company_id: str,
                   data_source_id: str, artifact_id: str, display_name: str,
                   definition: dict[str, Any], subject_id: str,
                   source_schema: str) -> dict[str, Any]:
    """Crea la plantilla y su primera version, en borrador."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.column_mapping (mapping_id, company_id, "
            "data_source_id, display_name, created_by) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s) RETURNING mapping_id",
            (company_id, data_source_id, display_name, subject_id))
        mapping_id = str(cursor.fetchone()[0])
        cursor.execute(
            "INSERT INTO fincilia.column_mapping_version (mapping_version_id, "
            "company_id, mapping_id, version_number, artifact_id, definition, "
            "definition_digest, source_schema_digest, created_by) "
            "VALUES (gen_random_uuid(), %s, %s, 1, %s, %s::jsonb, %s, %s, %s) "
            "RETURNING mapping_version_id",
            (company_id, mapping_id, artifact_id, json.dumps(definition),
             definition_digest(definition), source_schema, subject_id))
        version_id = str(cursor.fetchone()[0])
    return {"mapping_id": mapping_id, "mapping_version_id": version_id,
            "version_number": 1, "state": "draft"}


def load_mapping_version(connection: psycopg.Connection,
                         mapping_version_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT v.mapping_version_id, v.mapping_id, v.version_number, "
            "       v.artifact_id, v.definition, v.definition_digest, "
            "       v.source_schema_digest, v.state, v.created_by, v.created_at, "
            "       v.validated_by, m.display_name, m.data_source_id "
            "FROM fincilia.column_mapping_version v "
            "JOIN fincilia.column_mapping m ON m.mapping_id = v.mapping_id "
            "WHERE v.mapping_version_id = %s", (mapping_version_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return {"mapping_version_id": str(row[0]), "mapping_id": str(row[1]),
            "version_number": row[2], "artifact_id": str(row[3]),
            "definition": row[4], "definition_digest": row[5],
            "source_schema_digest": row[6], "state": row[7],
            "created_by": str(row[8]), "created_at": row[9].isoformat(),
            "validated_by": str(row[10]) if row[10] else None,
            "display_name": row[11], "data_source_id": str(row[12])}


def list_mappings(connection: psycopg.Connection, *,
                  artifact_id: str | None = None) -> list[dict[str, Any]]:
    statement = (
        "SELECT v.mapping_version_id, v.mapping_id, v.version_number, "
        "       v.artifact_id, v.state, m.display_name, v.created_at "
        "FROM fincilia.column_mapping_version v "
        "JOIN fincilia.column_mapping m ON m.mapping_id = v.mapping_id ")
    params: tuple = ()
    if artifact_id:
        statement += "WHERE v.artifact_id = %s "
        params = (artifact_id,)
    statement += "ORDER BY v.created_at DESC LIMIT 100"
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return [{"mapping_version_id": str(row[0]), "mapping_id": str(row[1]),
                 "version_number": row[2], "artifact_id": str(row[3]),
                 "state": row[4], "display_name": row[5],
                 "created_at": row[6].isoformat()} for row in cursor]


def record_decision(connection: psycopg.Connection, *, company_id: str,
                    mapping_version_id: str, ambiguity_kind: str, subject_ref: str,
                    resolved_value: str, rationale: str,
                    subject_id: str) -> dict[str, Any]:
    """Deja escrita la eleccion de una persona sobre una ambiguedad."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.mapping_decision (decision_id, company_id, "
            "mapping_version_id, ambiguity_kind, subject_ref, resolved_value, "
            "rationale, decided_by) VALUES (gen_random_uuid(), %s, %s, %s, %s, "
            "%s, %s, %s) "
            "ON CONFLICT (mapping_version_id, ambiguity_kind, subject_ref) "
            "DO NOTHING RETURNING decision_id",
            (company_id, mapping_version_id, ambiguity_kind, subject_ref,
             resolved_value, rationale, subject_id))
        row = cursor.fetchone()
        if row is not None:
            return {"decision_id": str(row[0]), "created": True}
        # Ya estaba decidida. Cambiar de opinion es una version de mapeo nueva,
        # no una reescritura de la fila que sostiene lo ya publicado.
        cursor.execute(
            "SELECT decision_id FROM fincilia.mapping_decision "
            "WHERE mapping_version_id = %s AND ambiguity_kind = %s "
            "AND subject_ref = %s",
            (mapping_version_id, ambiguity_kind, subject_ref))
        existing = cursor.fetchone()
    return {"decision_id": str(existing[0]) if existing else None, "created": False}


def list_decisions(connection: psycopg.Connection,
                   mapping_version_id: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT decision_id, ambiguity_kind, subject_ref, resolved_value, "
            "       rationale, decided_by, decided_at "
            "FROM fincilia.mapping_decision WHERE mapping_version_id = %s "
            "ORDER BY decided_at", (mapping_version_id,))
        return [{"decision_id": str(row[0]), "ambiguity_kind": row[1],
                 "subject_ref": row[2], "resolved_value": row[3],
                 "rationale": row[4], "decided_by": str(row[5]),
                 "decided_at": row[6].isoformat()} for row in cursor]


def validate_mapping_version(connection: psycopg.Connection, *,
                             mapping_version_id: str, subject_id: str) -> bool:
    """Pasa una version de borrador a validada. Idempotente."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.column_mapping_version "
            "SET state = 'validated', validated_by = %s, validated_at = now() "
            "WHERE mapping_version_id = %s AND state = 'draft'",
            (subject_id, mapping_version_id))
        return cursor.rowcount > 0


def resolvable_as(finding, mapping: ColumnMapping,
                  by_index: dict[int, dict[str, Any]]) -> tuple[str, str]:
    """Que decision resolveria este hallazgo, y sobre que.

    Devuelve `("", "")` si no lo resuelve ninguna: un mapeo sin columna de fecha
    no se arregla con una explicacion, y ofrecer un formulario para eso seria
    prometer una salida que no existe.
    """
    if finding.code != "MAP-AMBIGUOUS-COLUMN":
        return ("", "")
    field = finding.location.split(" -> ")[0].strip()
    index = mapping.column_of(field)
    if index is None:
        return ("", "")
    inferred = str((by_index.get(int(index)) or {}).get("inferred_type", ""))
    return (AMBIGUITY_KINDS.get(inferred, ""), field)


def blockers_for(mapping: ColumnMapping, profile: dict[str, Any],
                 decisions: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Lo que impide publicar, ya descontado lo que una persona resolvio.

    Un hallazgo resoluble desaparece cuando existe la decision que lo cubre **y**
    esa decision coincide con lo que el mapeo declara. Una eleccion que dice una
    cosa sobre un mapeo que hace otra no resuelve la ambiguedad: la documenta.
    """
    by_index = {int(column["index"]): column
                for column in (profile.get("columns") or [])
                if "index" in column}
    resolved = {(item["ambiguity_kind"], item["subject_ref"]): item["resolved_value"]
                for item in decisions}
    blockers: list[dict[str, str]] = []
    for finding in validate_mapping(mapping, profile):
        kind, subject = resolvable_as(finding, mapping, by_index)
        if kind:
            declared = DECLARED_BY_KIND[kind](mapping)
            if resolved.get((kind, subject)) == declared:
                continue
        blockers.append({"code": finding.code, "location": finding.location,
                         "detail": finding.detail,
                         "ambiguity_kind": kind, "subject_ref": subject,
                         "expected_value": DECLARED_BY_KIND[kind](mapping) if kind else "",
                         "resolvable": "true" if kind else "false"})
    return blockers


# --------------------------------------------------------------------------- #
# Preparacion
# --------------------------------------------------------------------------- #

def _release(connection: psycopg.Connection) -> dict[str, Any]:
    """La version del motor con la que se publica. Nunca `latest`."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT release_id, release_key, canonical_schema_version "
            "FROM fincilia.engine_release WHERE release_key = %s",
            (ENGINE_RELEASE_KEY,))
        row = cursor.fetchone()
    if row is None:
        raise PreparationError(
            "engine-release-missing",
            f"the engine release {ENGINE_RELEASE_KEY} is not registered; "
            "a dataset cannot claim to be reproducible without it")
    return {"release_id": str(row[0]), "release_key": row[1],
            "canonical_schema_version": row[2]}


def _existing_dataset(connection: psycopg.Connection, *, run_id: str,
                      mapping_version_id: str, release_id: str) -> dict | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT dataset_version_id, state, movement_count, rejected_count, "
            "       record_count FROM fincilia.dataset_version "
            "WHERE processing_run_id = %s AND mapping_version_id = %s "
            "AND engine_release_id = %s",
            (run_id, mapping_version_id, release_id))
        row = cursor.fetchone()
    if row is None:
        return None
    return {"dataset_version_id": str(row[0]), "state": row[1],
            "movement_count": row[2], "rejected_count": row[3],
            "record_count": row[4]}


def prepare_dataset(connection: psycopg.Connection, *, company_id: str,
                    artifact_id: str, mapping_version_id: str,
                    financial_account_id: str, subject_id: str,
                    timezone: str = "America/Bogota",
                    locale: str = "es-CO") -> Preparation:
    """Convierte las filas extraidas en movimientos canonicos, en una transaccion.

    Se escribe entero o no se escribe: el dataset, los registros de origen, los
    movimientos, los enlaces de evidencia, el grafo de linaje y el manifiesto
    reproducible. Un dataset a medias afirmaria un total que no cuadra con sus
    filas.

    Sale en `validated`, no en `published`: quien prepara no publica.
    """
    version = load_mapping_version(connection, mapping_version_id)
    if version is None:
        raise PreparationError("mapping-unknown", "no such mapping version")
    if version["state"] != "validated":
        raise PreparationError(
            "mapping-not-validated",
            "a draft mapping cannot produce a dataset; validate it first")

    extract_run = latest_run(connection, artifact_id, "extract")
    if extract_run is None:
        raise PreparationError(
            "not-extracted",
            "this document has no completed extraction; only promoted evidence "
            "is extracted, and quarantined evidence never is")
    profile_run = latest_run(connection, artifact_id, "profile")
    profile = (profile_run or {}).get("result") or {}

    # Reutilizar una plantilla en el extracto del mes siguiente es justo para lo
    # que sirve versionar un mapeo. Lo que **no** puede cambiar es la forma del
    # fichero: si cambia, los indices apuntan a otras columnas y nada falla.
    # Ese es exactamente el fallo que nadie ve, y por eso se compara la huella
    # del esquema y no el identificador del artefacto.
    if profile and schema_digest(profile) != version["source_schema_digest"]:
        raise PreparationError(
            "schema-drift",
            "the document no longer has the shape this mapping was written for",
            [{"code": "MAP-SCHEMA-DRIFT", "location": "columns",
              "detail": "the source schema digest changed", "resolvable": "false"}])
    if not profile and version["artifact_id"] != artifact_id:
        # Sin perfil no hay con que comparar. Aplicar la plantilla a ciegas
        # sobre otro fichero seria afirmar una compatibilidad que nadie ha
        # comprobado.
        raise PreparationError(
            "mapping-unverifiable",
            "this document has no profile, so a mapping written for another "
            "document cannot be checked against it")

    mapping = mapping_from_definition(version["definition"])
    decisions = list_decisions(connection, mapping_version_id)
    blockers = blockers_for(mapping, profile, decisions)
    if blockers:
        raise PreparationError(
            "unresolved-ambiguity",
            "the mapping still has unresolved findings; a person has to decide",
            blockers)

    release = _release(connection)
    reused = _existing_dataset(connection, run_id=extract_run["run_id"],
                               mapping_version_id=mapping_version_id,
                               release_id=release["release_id"])
    if reused is not None:
        # Misma entrada, mismo mapeo, misma version del motor: es el mismo
        # dataset. Preparar otra vez no duplica nada.
        return Preparation(dataset_version_id=reused["dataset_version_id"],
                           state=reused["state"],
                           movement_count=reused["movement_count"],
                           rejected_count=reused["rejected_count"],
                           record_count=reused["record_count"],
                           reused=True, rejections=())

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT raw_record_id, record_ordinal, raw_values, origin_locator "
            "FROM fincilia.raw_record WHERE processing_run_id = %s "
            "AND record_ordinal >= %s ORDER BY record_ordinal",
            (extract_run["run_id"], mapping.first_data_row))
        records = cursor.fetchall()
    if not records:
        raise PreparationError("no-data-rows",
                               "the declared range leaves no data rows")
    if len(records) > MAX_DATASET_ROWS:
        raise PreparationError(
            "dataset-too-large",
            f"a publication carries at most {MAX_DATASET_ROWS} rows and this one "
            f"has {len(records)}")

    prepared: list[tuple[dict[str, Any], Any]] = []
    rejections: list[dict[str, Any]] = []
    for raw_id, ordinal, values, locator in records:
        try:
            movement = apply_row(mapping, list(values), ordinal)
        except Exception as error:  # noqa: BLE001 - una fila rara no tumba el lote
            # El motivo lleva el numero de fila del fichero, que es como la
            # persona la encuentra. Nunca lleva el valor que fallo.
            rejections.append({
                "record_ordinal": ordinal, "code": "row_not_mappable",
                "detail": str(error) if isinstance(error, MappingError)
                else type(error).__name__})
            continue
        prepared.append(({"raw_record_id": str(raw_id), "record_ordinal": ordinal,
                          "locator": locator or {}}, movement))

    if not prepared:
        raise PreparationError("no-mappable-rows",
                               "not a single row could be read with this mapping")

    artifact_sha256 = str((records[0][3] or {}).get("artifact_sha256", ""))
    dataset_id = _write_dataset(
        connection, company_id=company_id, artifact_id=artifact_id,
        run_id=extract_run["run_id"], mapping_version_id=mapping_version_id,
        release=release, subject_id=subject_id, prepared=prepared,
        rejections=rejections, record_count=len(records),
        data_source_id=version["data_source_id"],
        financial_account_id=financial_account_id, mapping=mapping,
        artifact_sha256=artifact_sha256,
        definition_digest=version["definition_digest"],
        source_schema_digest=version["source_schema_digest"],
        timezone=timezone, locale=locale)

    return Preparation(dataset_version_id=dataset_id, state="validated",
                       movement_count=len(prepared),
                       rejected_count=len(rejections), record_count=len(records),
                       reused=False, rejections=tuple(rejections[:50]))


def _write_dataset(connection: psycopg.Connection, *, company_id: str,
                   artifact_id: str, run_id: str, mapping_version_id: str,
                   release: dict[str, Any], subject_id: str,
                   prepared: list[tuple[dict[str, Any], Any]],
                   rejections: list[dict[str, Any]], record_count: int,
                   data_source_id: str, financial_account_id: str,
                   mapping: ColumnMapping, artifact_sha256: str,
                   definition_digest: str, source_schema_digest: str,
                   timezone: str, locale: str) -> str:
    """Escribe el dataset entero. Todo dentro de la transaccion del llamante."""
    schema_version = release["canonical_schema_version"] or CANONICAL_SCHEMA_VERSION
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.dataset_version (dataset_version_id, company_id, "
            "processing_run_id, mapping_version_id, artifact_id, engine_release_id, "
            "canonical_schema_version, state, completeness_state, lineage_state, "
            "record_count, movement_count, rejected_count, prepared_by, "
            "validated_by, validated_at) VALUES (gen_random_uuid(), %s, %s, %s, %s, "
            "%s, %s, 'validated', %s, 'complete', %s, %s, %s, %s, %s, now()) "
            "RETURNING dataset_version_id",
            (company_id, run_id, mapping_version_id, artifact_id,
             release["release_id"], schema_version,
             # Una fila rechazada es un descuadre declarado, no un detalle.
             "verified" if not rejections else "mismatch",
             record_count, len(prepared), len(rejections), subject_id, subject_id))
        dataset_id = str(cursor.fetchone()[0])

        # El nodo terminal de evidencia: el artefacto y su huella.
        artifact_node = _node(cursor, company_id=company_id,
                              node_type="artifact_version", entity_ref=artifact_id,
                              field_name="", locator=None,
                              value_digest=artifact_sha256 or None,
                              release_id=release["release_id"],
                              schema_version=schema_version)

        for origin, movement in prepared:
            cursor.execute(
                "INSERT INTO fincilia.source_record (source_record_id, company_id, "
                "dataset_version_id, data_source_id, raw_record_id, record_family, "
                "source_payload, state, engine_release_id, canonical_schema_version, "
                "lineage_state) VALUES (gen_random_uuid(), %s, %s, %s, %s, "
                "'bank_statement_line', %s::jsonb, 'published', %s, %s, 'complete') "
                "RETURNING source_record_id",
                (company_id, dataset_id, data_source_id, origin["raw_record_id"],
                 json.dumps({"record_ordinal": origin["record_ordinal"],
                             "source_column": dict(movement.source_column)}),
                 release["release_id"], schema_version))
            source_record_id = str(cursor.fetchone()[0])

            amount = movement.amount
            cursor.execute(
                "INSERT INTO fincilia.canonical_movement (movement_id, company_id, "
                "dataset_version_id, source_record_id, financial_account_id, kind, "
                "amount, currency_code, direction, description, reference_original, "
                "reference_normalised, occurred_on, dedupe_fingerprint, state, "
                "engine_release_id, canonical_schema_version, lineage_state) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, 'other', %s, %s, %s, %s, "
                "%s, %s, %s, %s, 'proposed', %s, %s, 'complete') "
                "RETURNING movement_id",
                (company_id, dataset_id, source_record_id, financial_account_id,
                 amount, movement.currency, movement.direction,
                 movement.description or "(sin descripcion)",
                 movement.reference or None,
                 _normalise_reference(movement.reference),
                 movement.occurred_on,
                 _fingerprint(company_id, financial_account_id, movement),
                 release["release_id"], schema_version))
            movement_id = str(cursor.fetchone()[0])

            cursor.execute(
                "INSERT INTO fincilia.movement_evidence_link (link_id, company_id, "
                "movement_id, source_record_id, link_role, allocated_amount, "
                "currency_code, engine_release_id, canonical_schema_version, "
                "lineage_state) VALUES (gen_random_uuid(), %s, %s, %s, 'origin', "
                "%s, %s, %s, %s, 'complete')",
                (company_id, movement_id, source_record_id, amount,
                 movement.currency, release["release_id"], schema_version))

            _write_lineage(cursor, company_id=company_id, movement=movement,
                           movement_id=movement_id, origin=origin,
                           artifact_node=artifact_node, artifact_sha256=artifact_sha256,
                           mapping=mapping, release=release,
                           schema_version=schema_version, run_id=run_id,
                           subject_id=subject_id)

        manifest = {
            "canonical_schema_version": schema_version,
            "company_id": company_id,
            "deterministic_config": {
                "date_format": mapping.date_format,
                "decimal_format": mapping.decimal_format,
                "direction_mode": mapping.direction_mode,
                "first_data_row": mapping.first_data_row,
                "header_row": mapping.header_row,
            },
            "engine_release_key": release["release_key"],
            "input_artifact_sha256": artifact_sha256,
            "locale": locale,
            "mapping_definition_digest": definition_digest,
            "mapping_version_id": mapping_version_id,
            "random_seed": 0,
            "source_schema_digest": source_schema_digest,
            "timezone": timezone,
        }
        cursor.execute(
            "INSERT INTO fincilia.reproducibility_manifest (manifest_id, company_id, "
            "dataset_version_id, engine_release_id, input_artifact_sha256, "
            "mapping_version_id, deterministic_config, locale, timezone, "
            "random_seed, output_digests, reproduction_key) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s::jsonb, %s, %s, 0, "
            "%s::jsonb, %s)",
            (company_id, dataset_id, release["release_id"],
             artifact_sha256 or "0" * 64, mapping_version_id,
             json.dumps(manifest["deterministic_config"]), locale, timezone,
             json.dumps({"movements": digest_of(
                 [str(item[1].amount) for item in prepared])}),
             reproduction_key(manifest)))
    return dataset_id


def _node(cursor, *, company_id: str, node_type: str, entity_ref: str,
          field_name: str, locator: dict | None, value_digest: str | None,
          release_id: str, schema_version: str) -> str:
    """Inserta un nodo de linaje, o devuelve el que ya estaba.

    `field_name` no admite NULL: en un UNIQUE dos NULL no chocan, y el nodo del
    artefacto se duplicaria en silencio una vez por fila.
    """
    cursor.execute(
        "INSERT INTO fincilia.lineage_node (node_id, company_id, node_type, "
        "entity_ref, field_name, locator, value_digest, engine_release_id, "
        "canonical_schema_version) VALUES (gen_random_uuid(), %s, %s, %s, %s, "
        "%s::jsonb, %s, %s, %s) "
        "ON CONFLICT (company_id, node_type, entity_ref, field_name) DO NOTHING "
        "RETURNING node_id",
        (company_id, node_type, entity_ref, field_name,
         json.dumps(locator) if locator is not None else None,
         value_digest, release_id, schema_version))
    row = cursor.fetchone()
    if row is not None:
        return str(row[0])
    cursor.execute(
        "SELECT node_id FROM fincilia.lineage_node WHERE company_id = %s "
        "AND node_type = %s AND entity_ref = %s AND field_name = %s",
        (company_id, node_type, entity_ref, field_name))
    return str(cursor.fetchone()[0])


def _write_lineage(cursor, *, company_id: str, movement, movement_id: str,
                   origin: dict[str, Any], artifact_node: str, artifact_sha256: str,
                   mapping: ColumnMapping, release: dict[str, Any],
                   schema_version: str, run_id: str, subject_id: str) -> None:
    """Un camino por campo publicado: celda -> valor, con la operacion tipada.

    Cobertura del 100% de los campos publicados, no una media: el contrato dice
    `average_coverage_allowed: false`, y un campo sin camino bloquea. Cada arista
    `derived_from` nombra su transformacion, porque `derived_from` significa que
    el valor fluyo y no «esto tiene algo que ver con aquello».
    """
    release_id = release["release_id"]
    for field, column in sorted(movement.source_column.items()):
        cell = dict(origin["locator"])
        cell["field_ordinal"] = int(column)
        cell_node = _node(cursor, company_id=company_id, node_type="raw_locator",
                          entity_ref=origin["raw_record_id"], field_name=field,
                          locator=cell, value_digest=None, release_id=release_id,
                          schema_version=schema_version)
        fact_node = _node(cursor, company_id=company_id,
                          node_type="financial_fact_field", entity_ref=movement_id,
                          field_name=field, locator=None,
                          # La huella del valor, jamas el valor: un grafo que
                          # copia importes es una segunda base de datos que nadie
                          # protege.
                          value_digest=digest_of(getattr(movement, field, None)),
                          release_id=release_id, schema_version=schema_version)
        transform = TRANSFORMS.get(field, "verbatim")
        if field == "occurred_on":
            transform = f"parse_date:{mapping.date_format}"
        elif field == "amount":
            transform = f"normalise_amount:{mapping.decimal_format}"
        elif field == "direction":
            transform = f"resolve_direction:{mapping.direction_mode}"
        cursor.execute(
            "INSERT INTO fincilia.lineage_edge (edge_id, company_id, from_node_id, "
            "to_node_id, operation, transform_ref, actor_kind, actor_id, "
            "workload_identity, processing_run_id, engine_release_id, "
            "canonical_schema_version) VALUES (gen_random_uuid(), %s, %s, %s, "
            "'derived_from', %s, 'human', %s, 'api', %s, %s, %s) "
            "ON CONFLICT (from_node_id, to_node_id, operation) DO NOTHING",
            (company_id, cell_node, fact_node, transform, subject_id, run_id,
             release_id, schema_version))
        cursor.execute(
            "INSERT INTO fincilia.lineage_edge (edge_id, company_id, from_node_id, "
            "to_node_id, operation, actor_kind, actor_id, workload_identity, "
            "processing_run_id, engine_release_id, canonical_schema_version) "
            "VALUES (gen_random_uuid(), %s, %s, %s, 'included_in_snapshot', "
            "'service', %s, 'api', %s, %s, %s) "
            "ON CONFLICT (from_node_id, to_node_id, operation) DO NOTHING",
            (company_id, artifact_node, cell_node, subject_id, run_id, release_id,
             schema_version))


def _normalise_reference(reference: str | None) -> str | None:
    """Referencia comparable, sin espacios ni mayusculas.

    Es para buscar, no para identificar: hay indice y no UNIQUE. Dos cobros
    legitimos con la misma referencia existen, y colapsarlos seria perder dinero
    de vista.
    """
    if not reference:
        return None
    squeezed = " ".join(reference.split()).upper()
    return squeezed[:200] or None


def _fingerprint(company_id: str, account_id: str, movement) -> str:
    """Huella de deduplicacion. **No** es una restriccion unica.

    Sirve para que alguien pueda mirar candidatos, no para que el sistema decida
    que dos hechos son uno.
    """
    return digest_of({"account": account_id, "company": company_id,
                      "amount": str(movement.amount), "currency": movement.currency,
                      "direction": movement.direction,
                      "occurred_on": movement.occurred_on,
                      "reference": _normalise_reference(movement.reference) or ""})


# --------------------------------------------------------------------------- #
# Publicacion
# --------------------------------------------------------------------------- #

class PublicationError(Exception):
    """La publicacion no procede, y el motivo es del cliente."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def publish_dataset(connection: psycopg.Connection, *, dataset_version_id: str,
                    subject_id: str) -> dict[str, Any]:
    """Sella un dataset validado. Idempotente y segregada.

    Publicar no reescribe nada: los movimientos ya estaban, porque el revisor
    tiene que poder verlos antes de decidir. Lo que cambia es el estado, y con el
    la respuesta a «esto se puede usar».

    La segregacion se comprueba aqui **y** en un CHECK de la base. Duplicarla no
    es desconfianza: la de aqui da un mensaje util, y la de alla es la que
    aguanta cuando alguien llega por otro camino.
    """
    dataset = load_dataset(connection, dataset_version_id)
    if dataset is None:
        raise PublicationError("dataset-unknown", "no such dataset version")
    if dataset["state"] == "published":
        # Ya estaba publicado. Repetir la llamada no crea otra version ni cambia
        # quien la publico.
        return dataset
    if dataset["state"] != "validated":
        raise PublicationError(
            "dataset-not-validated",
            f"a dataset in {dataset['state']} cannot be published")
    if dataset["prepared_by"] == subject_id:
        raise PublicationError(
            "segregation-of-duties",
            "the subject who prepared this version cannot publish it")

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.dataset_version SET state = 'published', "
            "published_by = %s, published_at = now() "
            "WHERE dataset_version_id = %s AND state = 'validated'",
            (subject_id, dataset_version_id))
    published = load_dataset(connection, dataset_version_id)
    if published is None or published["state"] != "published":
        # Otro revisor llego primero y el estado ya no es `validated`. No es un
        # fallo si el desenlace es el mismo; lo es si acabo en otro sitio.
        raise PublicationError("dataset-not-validated",
                               "the dataset changed state while publishing")
    return published


def reject_dataset(connection: psycopg.Connection, *, dataset_version_id: str,
                   subject_id: str, reason: str) -> dict[str, Any]:
    """Rechaza un dataset validado. Tambien es una decision, y se audita."""
    dataset = load_dataset(connection, dataset_version_id)
    if dataset is None:
        raise PublicationError("dataset-unknown", "no such dataset version")
    if dataset["state"] not in ("draft", "validated"):
        raise PublicationError("dataset-not-validated",
                               f"a dataset in {dataset['state']} cannot be rejected")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.dataset_version SET state = 'rejected', "
            "rejected_reason = %s WHERE dataset_version_id = %s "
            "AND state IN ('draft', 'validated')",
            (reason[:200], dataset_version_id))
    return load_dataset(connection, dataset_version_id) or dataset


# --------------------------------------------------------------------------- #
# Lectura de lo publicado
# --------------------------------------------------------------------------- #

def load_dataset(connection: psycopg.Connection,
                 dataset_version_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT d.dataset_version_id, d.artifact_id, d.processing_run_id, "
            "       d.mapping_version_id, d.state, d.completeness_state, "
            "       d.lineage_state, d.record_count, d.movement_count, "
            "       d.rejected_count, d.prepared_by, d.prepared_at, "
            "       d.validated_by, d.published_by, d.published_at, "
            "       d.rejected_reason, d.canonical_schema_version, "
            "       e.release_key, m.reproduction_key, m.reproducible, "
            "       m.locale, m.timezone, m.deterministic_config "
            "FROM fincilia.dataset_version d "
            "JOIN fincilia.engine_release e ON e.release_id = d.engine_release_id "
            "LEFT JOIN fincilia.reproducibility_manifest m "
            "       ON m.dataset_version_id = d.dataset_version_id "
            "WHERE d.dataset_version_id = %s", (dataset_version_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return {
        "dataset_version_id": str(row[0]), "artifact_id": str(row[1]),
        "processing_run_id": str(row[2]), "mapping_version_id": str(row[3]),
        "state": row[4], "completeness_state": row[5], "lineage_state": row[6],
        "record_count": row[7], "movement_count": row[8], "rejected_count": row[9],
        "prepared_by": str(row[10]), "prepared_at": row[11].isoformat(),
        "validated_by": str(row[12]) if row[12] else None,
        "published_by": str(row[13]) if row[13] else None,
        "published_at": row[14].isoformat() if row[14] else None,
        "rejected_reason": row[15], "canonical_schema_version": row[16],
        "engine_release": row[17],
        "manifest": None if row[18] is None else {
            "reproduction_key": row[18], "reproducible": row[19],
            "locale": row[20], "timezone": row[21],
            "deterministic_config": row[22]},
    }


def list_datasets(connection: psycopg.Connection, *,
                  artifact_id: str | None = None,
                  limit: int = 50) -> list[dict[str, Any]]:
    statement = (
        "SELECT dataset_version_id, artifact_id, state, movement_count, "
        "       rejected_count, prepared_at, published_at "
        "FROM fincilia.dataset_version ")
    params: tuple = ()
    if artifact_id:
        statement += "WHERE artifact_id = %s "
        params = (artifact_id,)
    statement += "ORDER BY prepared_at DESC LIMIT %s"
    with connection.cursor() as cursor:
        cursor.execute(statement, params + (max(1, min(int(limit), 200)),))
        return [{"dataset_version_id": str(row[0]), "artifact_id": str(row[1]),
                 "state": row[2], "movement_count": row[3],
                 "rejected_count": row[4], "prepared_at": row[5].isoformat(),
                 "published_at": row[6].isoformat() if row[6] else None}
                for row in cursor]


def list_movements(connection: psycopg.Connection, *, dataset_version_id: str,
                   offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 200))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT m.movement_id, m.amount, m.currency_code, m.direction, "
            "       m.description, m.reference_original, m.occurred_on, "
            "       m.posted_on, m.value_date, m.accounting_date, m.state, "
            "       m.kind, r.record_ordinal "
            "FROM fincilia.canonical_movement m "
            "JOIN fincilia.source_record s ON s.source_record_id = m.source_record_id "
            "JOIN fincilia.raw_record r ON r.raw_record_id = s.raw_record_id "
            "WHERE m.dataset_version_id = %s ORDER BY r.record_ordinal "
            "LIMIT %s OFFSET %s", (dataset_version_id, limit, max(0, int(offset))))
        return [_movement_row(row) for row in cursor]


def _movement_row(row) -> dict[str, Any]:
    return {
        "movement_id": str(row[0]),
        # Punto fijo y cadena: serializar dinero como coma flotante es perderlo
        # en el unico sitio donde no se puede perder.
        "amount": f"{row[1]:.12f}", "currency": row[2], "direction": row[3],
        "description": row[4], "reference": row[5],
        "occurred_on": row[6].isoformat(),
        "posted_on": row[7].isoformat() if row[7] else None,
        "value_date": row[8].isoformat() if row[8] else None,
        "accounting_date": row[9].isoformat() if row[9] else None,
        "state": row[10], "kind": row[11], "record_ordinal": row[12],
    }


def load_movement(connection: psycopg.Connection,
                  movement_id: str) -> dict[str, Any] | None:
    """Un movimiento con su camino hasta la celda que lo produjo.

    Esto es lo que hace auditable un importe: no «viene de este fichero», sino
    «viene de la fila 42, columna 3, bytes 1180 a 1236 de este sha256, y la
    transformacion fue `normalise_amount:comma`».
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT m.movement_id, m.amount, m.currency_code, m.direction, "
            "       m.description, m.reference_original, m.occurred_on, "
            "       m.posted_on, m.value_date, m.accounting_date, m.state, "
            "       m.kind, r.record_ordinal, m.dataset_version_id, "
            "       r.origin_locator, r.raw_values, a.filename, d.state "
            "FROM fincilia.canonical_movement m "
            "JOIN fincilia.source_record s ON s.source_record_id = m.source_record_id "
            "JOIN fincilia.raw_record r ON r.raw_record_id = s.raw_record_id "
            "JOIN fincilia.source_artifact a ON a.artifact_id = r.artifact_id "
            "JOIN fincilia.dataset_version d "
            "       ON d.dataset_version_id = m.dataset_version_id "
            "WHERE m.movement_id = %s", (movement_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        payload = _movement_row(row)
        payload.update({
            "dataset_version_id": str(row[13]),
            "dataset_state": row[17],
            "origin": {"filename": row[16], "locator": row[14],
                       "values": row[15]},
        })
        cursor.execute(
            "SELECT fact.field_name, cell.locator, edge.transform_ref, "
            "       fact.value_digest, edge.operation "
            "FROM fincilia.lineage_node fact "
            "JOIN fincilia.lineage_edge edge ON edge.to_node_id = fact.node_id "
            "JOIN fincilia.lineage_node cell ON cell.node_id = edge.from_node_id "
            "WHERE fact.node_type = 'financial_fact_field' AND fact.entity_ref = %s "
            "AND edge.operation = 'derived_from' ORDER BY fact.field_name",
            (movement_id,))
        payload["lineage"] = [
            {"field": field, "cell": locator, "transform": transform,
             "value_digest": digest, "operation": operation}
            for field, locator, transform, digest, operation in cursor]
    return payload


# --------------------------------------------------------------------------- #
# Maestros de la empresa
# --------------------------------------------------------------------------- #

def list_accounts(connection: psycopg.Connection) -> list[dict[str, Any]]:
    """Las cuentas contra las que se registra un movimiento.

    Sale el token y los cuatro ultimos digitos, nunca el identificador completo:
    `canonical-model` tipa `identifier_token` como `tokenized_identifier`, y una
    lista de cuentas no es sitio para un numero de cuenta.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT account_id, account_family, display_name, identifier_last4, "
            "       currency_code, status FROM fincilia.financial_account "
            "WHERE status = 'active' ORDER BY display_name")
        return [{"account_id": str(row[0]), "account_family": row[1],
                 "display_name": row[2], "identifier_last4": row[3],
                 "currency_code": row[4], "status": row[5]} for row in cursor]


def list_sources(connection: psycopg.Connection) -> list[dict[str, Any]]:
    """De donde viene la evidencia: banco, pasarela, contabilidad."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_source_id, source_family, display_name, timezone, status "
            "FROM fincilia.data_source WHERE status = 'active' "
            "ORDER BY display_name")
        return [{"data_source_id": str(row[0]), "source_family": row[1],
                 "display_name": row[2], "timezone": row[3], "status": row[4]}
                for row in cursor]
