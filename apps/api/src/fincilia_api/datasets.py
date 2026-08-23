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

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

from fincilia_contracts.extraction import MAX_EXTRACT_ROWS
from fincilia_contracts.mapping import (
    CANONICAL_FIELDS,
    ColumnMapping,
    MappingError,
    apply_row,
    validate_mapping,
)
from fincilia_contracts.lineage import (
    LineageError,
    TransformStep,
    build_plan,
    plan_digest,
    reconstruct,
    validate_plan,
)
from fincilia_contracts.release import (
    CANONICAL_SCHEMA_VERSION,
    ENGINE_RELEASE_KEY,
    canonical_json,
    digest_of,
    reproduction_key,
)

logger = logging.getLogger("fincilia.api.datasets")

# Techo de una publicacion. Ya no es un numero arbitrario menor que el de la
# extraccion: es **el mismo**, porque preparar dejo de cargar el fichero entero
# en memoria. Se comprueba con un `count(*)` antes de traer una sola fila; la
# version anterior lo comprobaba despues de un `fetchall`, asi que el techo
# protegia la escritura y no la memoria.
MAX_DATASET_ROWS = MAX_EXTRACT_ROWS

# Filas por lote. Cada lote es una transaccion con su punto de control: mas
# grande amortiza mejor el viaje, mas pequeno pierde menos trabajo al reintentar.
CHUNK_SIZE = 2_000

# Cuanto trabaja una peticion antes de devolver `staging` y dejar que el llamante
# continue. Es la contrapresion: una peticion que dura minutos retiene una
# conexion del pool y no le sirve a nadie.
PREPARE_BUDGET_SECONDS = 25.0

# Cuantos motivos de rechazo se conservan para ensenar. La **cuenta** es exacta y
# sale de la base; esto es una muestra. Retener cien mil motivos para ensenar
# cincuenta es la clase de detalle que convierte una respuesta en un volcado.
MAX_REPORTED_REJECTIONS = 50

# Filas que trae de golpe el cursor de servidor al calcular la huella final.
DIGEST_BATCH = 1_000

# Cuantas filas devuelve como mucho una vista previa. La vista previa **si**
# lleva valores, y por eso pagina siempre: devolver el fichero entero por una
# peticion seria descargar la evidencia con otro nombre.
MAX_PREVIEW_LIMIT = 200
DEFAULT_PREVIEW_LIMIT = 50

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
    """Lo que se sabe de una preparacion, en conteos y nunca en payload."""

    dataset_version_id: str
    state: str
    movement_count: int
    rejected_count: int
    record_count: int
    reused: bool
    rejections: tuple[dict[str, Any], ...]
    complete: bool = True
    expected_record_count: int = 0
    chunks: int = 0
    last_record: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset_version_id": self.dataset_version_id, "state": self.state,
            "movement_count": self.movement_count,
            "rejected_count": self.rejected_count,
            "record_count": self.record_count, "reused": self.reused,
            "complete": self.complete,
            "expected_record_count": self.expected_record_count,
            "chunks": self.chunks,
            "rejections": list(self.rejections),
        }


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


def unaccounted_columns(definition: dict[str, Any], mapping: ColumnMapping,
                        profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Columnas del fichero que ni se usan ni se declararon ignoradas.

    No bloquea: una columna de saldo acumulado que nadie mapea es normal. Lo que
    no es normal es no haberla mirado. Declarar que se ignora deja escrito «la vi
    y decidi no usarla», que es distinto de «se me paso», y la diferencia importa
    cuando el que revisa no es el que mapeo.
    """
    declared = {int(index) for index in (definition.get("ignored_columns") or [])
                if isinstance(index, int)}
    used = set(mapping.columns.values())
    return [
        {"index": int(column["index"]), "header": str(column.get("header", "")),
         "inferred_type": str(column.get("inferred_type", ""))}
        for column in (profile.get("columns") or [])
        if "index" in column
        and int(column["index"]) not in used
        and int(column["index"]) not in declared
    ]


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

def approved_release(connection: psycopg.Connection,
                     release_key: str = ENGINE_RELEASE_KEY) -> dict[str, Any]:
    """La version del motor con la que se puede publicar hoy.

    Cuatro cosas tienen que darse, y ninguna es opcional:

    * la release existe y se llama por su nombre, nunca `latest`;
    * su estado es `approved`. `draft` no publica —nadie ha mirado que produce— y
      `superseded` tampoco: reproduce lo que ya salio de ella, pero no empieza
      nada nuevo;
    * tiene referencia de aprobacion, que es quien responde de ella;
    * **lo aprobado es lo que corre.** Si los componentes cambiaron despues de la
      firma, la firma cubria otra cosa. Un disparador de la base lo impide, y
      esto lo vuelve a comprobar al leer: una integridad que solo se comprueba en
      un sitio es una integridad que se pierde el dia que ese sitio falla.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT r.release_id, r.release_key, r.canonical_schema_version, "
            "       r.state, r.approval_ref, r.components, a.components_digest, "
            "       a.actor_identity, a.occurred_at "
            "FROM fincilia.engine_release r "
            "LEFT JOIN fincilia.release_approval a "
            "       ON a.release_id = r.release_id AND a.action = 'approved' "
            "WHERE r.release_key = %s", (release_key,))
        row = cursor.fetchone()

    if row is None:
        raise PreparationError(
            "engine-release-missing",
            f"the engine release {release_key} is not registered; a dataset "
            "cannot claim to be reproducible against a release that does not exist")
    state = row[3]
    if state != "approved":
        raise PreparationError(
            "engine-release-not-approved",
            f"the engine release {release_key} is in {state}; publishing needs an "
            "approved release, and approving one is a human decision this service "
            "does not take")
    if not row[4] or row[6] is None:
        raise PreparationError(
            "engine-release-unattested",
            f"the engine release {release_key} says it is approved but carries no "
            "record of who approved it")
    if digest_of(row[5] or []) != row[6]:
        raise PreparationError(
            "engine-release-tampered",
            f"the components of {release_key} changed after it was approved; the "
            "approval covered something else")

    return {"release_id": str(row[0]), "release_key": row[1],
            "canonical_schema_version": row[2], "state": state,
            "approval_ref": row[4], "approved_by": row[7],
            "approved_at": row[8].isoformat() if row[8] else None}


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


def _preparation_context(connection: psycopg.Connection, *, company_id: str,
                         artifact_id: str, mapping_version_id: str,
                         release_key: str) -> dict[str, Any]:
    """Todo lo que hay que comprobar **antes** de tocar una sola fila.

    Se hace en una lectura corta y aparte a proposito: si algo bloquea, bloquea
    sin haber reservado memoria ni haber abierto una transaccion larga.
    """
    version = load_mapping_version(connection, mapping_version_id)
    if version is None:
        raise PreparationError("mapping-unknown", "no such mapping version")
    if version["state"] not in ("validated", "superseded"):
        raise PreparationError(
            "mapping-not-validated",
            "a draft mapping cannot produce a dataset; validate it first")

    extract_run = latest_run(connection, artifact_id, "extract")
    if extract_run is None:
        raise PreparationError(
            "not-extracted",
            "this document has no completed extraction; only promoted evidence "
            "is extracted, and quarantined evidence never is")

    # Una lectura truncada **termina bien**: `truncated` es un estado, no un
    # fallo, porque el fichero se leyo hasta donde se pudo y decirlo es mejor que
    # fingir un error. Lo que no puede pasar es publicarla como si estuviera
    # entera: el total cuadraria consigo mismo y le faltarian filas.
    summary = extract_run["result"] or {}
    if summary.get("truncated"):
        raise PreparationError(
            "extraction-truncated",
            "the extraction stopped before the end of the file "
            f"({summary.get('truncation_reason') or 'unknown reason'}); publishing "
            "it would report a total that is missing rows",
            [{"code": "EXTRACT-TRUNCATED", "location": "extraction",
              "detail": str(summary.get("truncation_reason") or ""),
              "resolvable": "false"}])

    profile_run = latest_run(connection, artifact_id, "profile")
    profile = (profile_run or {}).get("result") or {}

    # Reutilizar una plantilla en el extracto del mes siguiente es justo para lo
    # que sirve versionar un mapeo. Lo que **no** puede cambiar es la forma del
    # fichero: si cambia, los indices apuntan a otras columnas y nada falla.
    if profile and schema_digest(profile) != version["source_schema_digest"]:
        raise PreparationError(
            "schema-drift",
            "the document no longer has the shape this mapping was written for",
            [{"code": "MAP-SCHEMA-DRIFT", "location": "columns",
              "detail": "the source schema digest changed", "resolvable": "false"}])
    if not profile and version["artifact_id"] != artifact_id:
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

    release = approved_release(connection, release_key)
    plan = _plan_for(connection, company_id=company_id,
                     mapping_version_id=mapping_version_id, release=release,
                     mapping=mapping, delimiter=str(summary.get("delimiter") or ","),
                     decided_fields=frozenset(item["subject_ref"] for item in decisions))

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT content_sha256 FROM fincilia.source_artifact "
            "WHERE artifact_id = %s", (artifact_id,))
        row = cursor.fetchone()

    return {
        "artifact_id": artifact_id,
        "artifact_sha256": str(row[0]) if row else "",
        "run_id": extract_run["run_id"],
        "mapping": mapping,
        "mapping_version_id": mapping_version_id,
        "definition_digest": version["definition_digest"],
        "source_schema_digest": version["source_schema_digest"],
        "data_source_id": version["data_source_id"],
        "decisions": decisions,
        "release": release,
        "plan": plan,
    }


def linked_account(connection: psycopg.Connection, *, data_source_id: str,
                   financial_account_id: str | None = None) -> str:
    """La cuenta contra la que esta fuente registra movimientos.

    Se exige el vinculo en vez de aceptar cualquier cuenta de la empresa. Un
    extracto bancario que aterriza en la cuenta de otra pasarela cuadra consigo
    mismo y descuadra el cierre, y nadie lo nota hasta que alguien concilia.

    Con `financial_account_id` comprueba que ese vinculo existe y esta vivo; sin
    el devuelve el principal, que es lo que permite reanudar una preparacion sin
    volver a pedir el dato.
    """
    with connection.cursor() as cursor:
        if financial_account_id:
            cursor.execute(
                "SELECT financial_account_id, relation_role "
                "FROM fincilia.data_source_account "
                "WHERE data_source_id = %s AND financial_account_id = %s "
                "AND status = 'active' "
                "AND (valid_to IS NULL OR valid_to >= CURRENT_DATE) LIMIT 1",
                (data_source_id, financial_account_id))
            row = cursor.fetchone()
            if row is None:
                raise PreparationError(
                    "account-not-linked",
                    "this account is not linked to the data source of this mapping; "
                    "link them first, or pick the account the source settles into")
        else:
            cursor.execute(
                "SELECT financial_account_id, relation_role "
                "FROM fincilia.data_source_account "
                "WHERE data_source_id = %s AND relation_role = 'primary' "
                "AND status = 'active' LIMIT 1", (data_source_id,))
            row = cursor.fetchone()
            if row is None:
                raise PreparationError(
                    "source-without-account",
                    "this data source has no primary account; a movement always "
                    "happens against one")

        account_id = str(row[0])
        cursor.execute(
            "SELECT status FROM fincilia.financial_account WHERE account_id = %s",
            (account_id,))
        status = cursor.fetchone()
        cursor.execute(
            "SELECT status FROM fincilia.data_source WHERE data_source_id = %s",
            (data_source_id,))
        source_status = cursor.fetchone()

    # Una cuenta suspendida o cerrada no recibe movimientos nuevos. Lo publicado
    # con ella se conserva: cerrar una cuenta no borra su historia.
    if not status or status[0] != "active":
        raise PreparationError(
            "account-not-active",
            f"the account is {status[0] if status else 'missing'}; a suspended or "
            "closed account does not take new publications")
    if not source_status or source_status[0] != "active":
        raise PreparationError(
            "source-not-active",
            f"the data source is {source_status[0] if source_status else 'missing'}")
    return account_id


def _plan_for(connection: psycopg.Connection, *, company_id: str,
              mapping_version_id: str, release: dict[str, Any],
              mapping: ColumnMapping, delimiter: str,
              decided_fields: frozenset[str]) -> dict[str, Any]:
    """El plan de transformacion de este mapeo con esta version del motor.

    Idempotente por `(mapping_version_id, engine_release_id)`: preparar dos veces
    reutiliza el plan, y cambiar la transformacion cambia el par, luego es otro
    plan y el anterior sigue existiendo para reconstruir lo que ya publico.
    """
    steps = build_plan(mapping, engine_release_key=release["release_key"],
                       delimiter=delimiter, decided_fields=decided_fields)
    problems = validate_plan(steps, frozenset(mapping.columns))
    if problems:
        # `on_incomplete: block_publication`. Un campo publicado sin sus seis
        # etapas no se puede auditar, y publicarlo seria afirmar que si.
        raise PreparationError(
            "lineage-incomplete",
            "the lineage plan does not reconstruct every stage of every field",
            [{"code": "LIN-INCOMPLETE", "location": "plan", "detail": problem,
              "resolvable": "false"} for problem in problems])

    digest = plan_digest(steps)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT plan_id, plan_digest FROM fincilia.lineage_transform_plan "
            "WHERE mapping_version_id = %s AND engine_release_id = %s",
            (mapping_version_id, release["release_id"]))
        row = cursor.fetchone()
        if row is not None:
            if row[1] != digest:
                # El plan guardado dice otra cosa que el que produce este codigo.
                # Reconstruir con el nuevo seria explicar lo publicado con reglas
                # que no lo produjeron.
                raise PreparationError(
                    "lineage-plan-drift",
                    "the stored transform plan for this mapping and release differs "
                    "from the one this engine builds; reproducing with it would "
                    "explain the data with rules that did not produce it")
            return {"plan_id": str(row[0]), "steps": steps, "digest": digest}

        cursor.execute(
            "INSERT INTO fincilia.lineage_transform_plan (plan_id, company_id, "
            "mapping_version_id, engine_release_id, plan_digest, "
            "canonical_schema_version, field_count) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s) "
            "RETURNING plan_id",
            (company_id, mapping_version_id, release["release_id"], digest,
             release["canonical_schema_version"], len(mapping.columns)))
        plan_id = str(cursor.fetchone()[0])
        cursor.executemany(
            "INSERT INTO fincilia.lineage_transform_step (step_id, company_id, "
            "plan_id, canonical_field, step_ordinal, stage, operation, "
            "input_semantic_type, output_semantic_type, transform_ref, "
            "configuration_digest, parser_version, rule_version, source_column) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
            "%s, %s, %s)",
            [(company_id, plan_id, step.canonical_field, step.step_ordinal,
              step.stage, step.operation, step.input_semantic_type,
              step.output_semantic_type, step.transform_ref,
              step.configuration_digest, step.parser_version, step.rule_version,
              step.source_column) for step in steps])
    return {"plan_id": plan_id, "steps": steps, "digest": digest}


def _count_records(connection: psycopg.Connection, run_id: str,
                   first_data_row: int) -> int:
    """Cuantas filas hay que preparar, **antes** de traer ninguna.

    La version anterior contaba despues de un `fetchall`: el techo protegia la
    escritura y no la memoria, asi que un fichero de cien mil filas reservaba
    doscientos megabytes y despues decia que era demasiado grande.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM fincilia.raw_record "
            "WHERE processing_run_id = %s AND record_ordinal >= %s",
            (run_id, first_data_row))
        return int(cursor.fetchone()[0])


def _resume_point(connection: psycopg.Connection,
                  dataset_version_id: str) -> tuple[int, int]:
    """Por donde sigue una preparacion interrumpida: `(siguiente lote, ordinal)`.

    La fila de `dataset_chunk` entra en la misma transaccion que sus movimientos,
    asi que si esta, el lote entero esta. Su ausencia es igual de informativa: lo
    que no figura, no ocurrio.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(max(chunk_ordinal) + 1, 0), coalesce(max(last_record), 0) "
            "FROM fincilia.dataset_chunk WHERE dataset_version_id = %s",
            (dataset_version_id,))
        row = cursor.fetchone()
    return int(row[0]), int(row[1])


def _stage_dataset(connection: psycopg.Connection, *, company_id: str,
                   artifact_id: str, run_id: str, mapping_version_id: str,
                   release: dict[str, Any], plan_id: str, subject_id: str,
                   expected: int) -> tuple[str, str]:
    """Crea o recupera el dataset en `staging`. Devuelve `(id, estado)`.

    `staging` existe para que un dataset a medias **nunca** parezca publicado.
    Sin ese estado, la unica forma de que no lo pareciera seria una transaccion
    que abarcara las cien mil filas, que es lo que este rediseno quita.
    """
    existing = _existing_dataset(connection, run_id=run_id,
                                mapping_version_id=mapping_version_id,
                                release_id=release["release_id"])
    if existing is not None:
        return existing["dataset_version_id"], existing["state"]

    with connection.cursor() as cursor:
        try:
            with connection.transaction():
                cursor.execute(
                    "INSERT INTO fincilia.dataset_version (dataset_version_id, "
                    "company_id, processing_run_id, mapping_version_id, artifact_id, "
                    "engine_release_id, lineage_plan_id, canonical_schema_version, "
                    "state, completeness_state, lineage_state, record_count, "
                    "expected_record_count, movement_count, rejected_count, "
                    "prepared_by) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, "
                    "%s, 'staging', 'unknown', 'required_pending', 0, %s, 0, 0, %s) "
                    "RETURNING dataset_version_id",
                    (company_id, run_id, mapping_version_id, artifact_id,
                     release["release_id"], plan_id,
                     release["canonical_schema_version"], expected, subject_id))
                return str(cursor.fetchone()[0]), "staging"
        except psycopg.errors.UniqueViolation:
            # Otra peticion lo creo entre la lectura y la escritura. Es el mismo
            # dataset: la terna es su identidad.
            found = _existing_dataset(connection, run_id=run_id,
                                      mapping_version_id=mapping_version_id,
                                      release_id=release["release_id"])
            if found is None:
                raise
            return found["dataset_version_id"], found["state"]


def _seal_artifact(cursor, *, company_id: str, artifact_id: str,
                   artifact_sha256: str, release: dict[str, Any],
                   run_id: str, subject_id: str, dataset_version_id: str) -> None:
    """El unico nodo de grafo por dataset: la evidencia terminal y su sello.

    Todo lo demas se reconstruye. Esto no: que **este** artefacto quedo sellado
    dentro de **este** dataset es un hecho del grafo, y es de cardinalidad uno.
    """
    schema_version = release["canonical_schema_version"]
    artifact_node = _node(cursor, company_id=company_id,
                          node_type="artifact_version", entity_ref=artifact_id,
                          field_name="", locator=None,
                          value_digest=artifact_sha256 or None,
                          release_id=release["release_id"],
                          schema_version=schema_version)
    dataset_node = _node(cursor, company_id=company_id,
                         node_type="source_record_field",
                         entity_ref=dataset_version_id, field_name="dataset",
                         locator=None, value_digest=None,
                         release_id=release["release_id"],
                         schema_version=schema_version)
    cursor.execute(
        "INSERT INTO fincilia.lineage_edge (edge_id, company_id, from_node_id, "
        "to_node_id, operation, actor_kind, actor_id, workload_identity, "
        "processing_run_id, engine_release_id, canonical_schema_version) "
        "VALUES (gen_random_uuid(), %s, %s, %s, 'included_in_snapshot', 'human', "
        "%s, 'api', %s, %s, %s) "
        "ON CONFLICT (from_node_id, to_node_id, operation) DO NOTHING",
        (company_id, artifact_node, dataset_node, subject_id, run_id,
         release["release_id"], schema_version))


def _seal_decisions(cursor, *, company_id: str, decisions: list[dict[str, Any]],
                    dataset_version_id: str, release: dict[str, Any],
                    run_id: str, subject_id: str) -> None:
    """`decided_using`: una decision humana entro en este dataset sin derivar valor.

    Es la operacion que el contrato distingue de `derived_from` a proposito, y
    mezclarlas borraria la diferencia entre «esto se calculo» y «alguien eligio».
    """
    schema_version = release["canonical_schema_version"]
    dataset_node = _node(cursor, company_id=company_id,
                         node_type="source_record_field",
                         entity_ref=dataset_version_id, field_name="dataset",
                         locator=None, value_digest=None,
                         release_id=release["release_id"],
                         schema_version=schema_version)
    for decision in decisions:
        decision_node = _node(cursor, company_id=company_id, node_type="decision",
                              entity_ref=decision["decision_id"],
                              field_name=decision["subject_ref"][:64], locator=None,
                              value_digest=digest_of(decision["resolved_value"]),
                              release_id=release["release_id"],
                              schema_version=schema_version)
        cursor.execute(
            "INSERT INTO fincilia.lineage_edge (edge_id, company_id, from_node_id, "
            "to_node_id, operation, actor_kind, actor_id, workload_identity, "
            "processing_run_id, engine_release_id, canonical_schema_version) "
            "VALUES (gen_random_uuid(), %s, %s, %s, 'decided_using', 'human', %s, "
            "'api', %s, %s, %s) "
            "ON CONFLICT (from_node_id, to_node_id, operation) DO NOTHING",
            (company_id, decision_node, dataset_node, subject_id, run_id,
             release["release_id"], schema_version))


def _write_chunk(connection: psycopg.Connection, *, company_id: str,
                 dataset_version_id: str, chunk_ordinal: int,
                 rows: list[tuple], mapping: ColumnMapping,
                 data_source_id: str, financial_account_id: str,
                 release: dict[str, Any]) -> tuple[int, int, list[dict[str, Any]]]:
    """Un lote entero en una transaccion: registros, movimientos y enlaces.

    Tres sentencias multifila en vez de veintitres por fila. Los identificadores
    se generan aqui y no con `RETURNING`: sin eso cada fila costaria un viaje de
    ida y vuelta, y cien mil filas costarian dos millones y medio.

    **No es `COPY`**, y no por gusto: PostgreSQL no admite `COPY FROM` sobre una
    tabla con seguridad por filas, que es justo lo que protege estas tres. Entre
    perder el aislamiento y perder algo de velocidad, se pierde velocidad.
    """
    schema_version = release["canonical_schema_version"]
    release_id = release["release_id"]

    records: list[tuple] = []
    movements: list[tuple] = []
    links: list[tuple] = []
    rejections: list[dict[str, Any]] = []

    for raw_id, ordinal, values, locator in rows:
        try:
            movement = apply_row(mapping, list(values), ordinal)
        except Exception as error:  # noqa: BLE001 - una fila rara no tumba el lote
            rejections.append({
                "record_ordinal": ordinal, "code": "row_not_mappable",
                "detail": str(error) if isinstance(error, MappingError)
                else type(error).__name__})
            continue

        source_record_id = str(uuid.uuid4())
        movement_id = str(uuid.uuid4())
        reference = _normalise_reference(movement.reference)
        # Huellas por campo publicado: es la etapa terminal del linaje, y cabe en
        # la propia fila. Nunca el valor.
        digests = {field: digest_of(getattr(movement, field, None))
                   for field in sorted(movement.source_column)}

        records.append((
            source_record_id, company_id, dataset_version_id, data_source_id,
            str(raw_id), "bank_statement_line",
            dumps_compact({"record_ordinal": ordinal,
                           "source_column": dict(movement.source_column)}),
            "published", release_id, schema_version, "complete"))
        movements.append((
            movement_id, company_id, dataset_version_id, source_record_id,
            financial_account_id, "other", f"{movement.amount:.12f}",
            movement.currency, movement.direction,
            movement.description or "(sin descripcion)",
            movement.reference or None, reference, movement.occurred_on,
            _fingerprint(company_id, financial_account_id, movement), "proposed",
            release_id, schema_version, "complete", dumps_compact(digests)))
        links.append((
            str(uuid.uuid4()), company_id, movement_id, source_record_id, "origin",
            f"{movement.amount:.12f}", movement.currency, release_id,
            schema_version, "complete"))

    first = int(rows[0][1])
    last = int(rows[-1][1])
    with connection.cursor() as cursor:
        if records:
            insert_many(
                cursor,
                "INSERT INTO fincilia.source_record (source_record_id, company_id, "
                "dataset_version_id, data_source_id, raw_record_id, record_family, "
                "source_payload, state, engine_release_id, canonical_schema_version, "
                "lineage_state) VALUES ",
                "(%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)", records)
            insert_many(
                cursor,
                "INSERT INTO fincilia.canonical_movement (movement_id, company_id, "
                "dataset_version_id, source_record_id, financial_account_id, kind, "
                "amount, currency_code, direction, description, reference_original, "
                "reference_normalised, occurred_on, dedupe_fingerprint, state, "
                "engine_release_id, canonical_schema_version, lineage_state, "
                "field_digests) VALUES ",
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "%s, %s, %s::jsonb)", movements)
            insert_many(
                cursor,
                "INSERT INTO fincilia.movement_evidence_link (link_id, company_id, "
                "movement_id, source_record_id, link_role, allocated_amount, "
                "currency_code, engine_release_id, canonical_schema_version, "
                "lineage_state) VALUES ",
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", links)
        # El punto de control va **con** los datos, no despues: si esta la fila,
        # esta el lote, y si no esta, el lote no ocurrio.
        cursor.execute(
            "INSERT INTO fincilia.dataset_chunk (chunk_id, company_id, "
            "dataset_version_id, chunk_ordinal, first_record, last_record, "
            "movement_count, rejected_count) VALUES (gen_random_uuid(), %s, %s, "
            "%s, %s, %s, %s, %s)",
            (company_id, dataset_version_id, chunk_ordinal, first, last,
             len(movements), len(rejections)))
    return len(movements), len(rejections), rejections


# Filas por sentencia. Cada fila lleva hasta diecinueve parametros, y PostgreSQL
# admite 65.535 por sentencia: quinientas dejan un margen amplio y siguen
# amortizando el viaje.
INSERT_BATCH = 500


def insert_many(cursor, prefix: str, template: str, rows: list[tuple]) -> None:
    """Inserta en tandas con una sola sentencia por tanda.

    Los valores siguen siendo parametros: lo unico que se construye es la lista
    de huecos. Interpolar valores aqui seria cambiar un problema de rendimiento
    por uno de inyeccion.
    """
    for start in range(0, len(rows), INSERT_BATCH):
        batch = rows[start:start + INSERT_BATCH]
        cursor.execute(prefix + ", ".join([template] * len(batch)),
                       [value for row in batch for value in row])


def dumps_compact(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


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


def prepare_dataset(database, *, company_id: str, artifact_id: str,
                    mapping_version_id: str, financial_account_id: str,
                    subject_id: str, release_key: str = ENGINE_RELEASE_KEY,
                    timezone: str = "America/Bogota", locale: str = "es-CO",
                    chunk_size: int = CHUNK_SIZE,
                    time_budget: float = PREPARE_BUDGET_SECONDS) -> Preparation:
    """Convierte las filas extraidas en movimientos canonicos, por lotes.

    **No es una transaccion.** Serlo obligaria a sostener cien mil filas en
    memoria y una conexion abierta durante todo el trabajo, que es exactamente lo
    que hacia la version anterior y por lo que tenia un techo de diez mil.

    En su lugar: el dataset nace en `staging` —invisible como publicado—, cada
    lote entra en su propia transaccion junto a su punto de control, y el paso
    final lo pasa a `validated` de una vez. Si el proceso se cae en medio, lo que
    entro esta y el resto se reanuda desde el ultimo lote; si nunca se reanuda,
    se queda en `staging`, que es la respuesta correcta a «esto esta a medias».

    Devuelve `state='staging'` cuando se agota el presupuesto de tiempo: el
    llamante continua. Sale en `validated` y jamas en `published`: quien prepara
    no publica.
    """
    started = time.monotonic()
    with database.session(company_id=company_id, subject_id=subject_id) as connection:
        context = _preparation_context(
            connection, company_id=company_id, artifact_id=artifact_id,
            mapping_version_id=mapping_version_id, release_key=release_key)
        context["financial_account_id"] = linked_account(
            connection, data_source_id=context["data_source_id"],
            financial_account_id=financial_account_id)
        expected = _count_records(connection, context["run_id"],
                                  context["mapping"].first_data_row)
        if expected == 0:
            raise PreparationError("no-data-rows",
                                   "the declared range leaves no data rows")
        if expected > MAX_DATASET_ROWS:
            raise PreparationError(
                "dataset-too-large",
                f"a publication carries at most {MAX_DATASET_ROWS} rows and this "
                f"one has {expected}")
        dataset_id, state = _stage_dataset(
            connection, company_id=company_id, artifact_id=artifact_id,
            run_id=context["run_id"], mapping_version_id=mapping_version_id,
            release=context["release"], plan_id=context["plan"]["plan_id"],
            subject_id=subject_id, expected=expected)

    if state not in ("staging", "draft"):
        # Ya estaba terminado. Preparar otra vez no duplica nada.
        with database.session(company_id=company_id,
                              subject_id=subject_id) as connection:
            done = load_dataset(connection, dataset_id) or {}
        return Preparation(dataset_version_id=dataset_id, state=state,
                           movement_count=int(done.get("movement_count", 0)),
                           rejected_count=int(done.get("rejected_count", 0)),
                           record_count=int(done.get("record_count", 0)),
                           reused=True, rejections=(), complete=True,
                           expected_record_count=expected)

    return _drive_chunks(database, company_id=company_id, subject_id=subject_id,
                         dataset_id=dataset_id, context=context, expected=expected,
                         chunk_size=chunk_size, time_budget=time_budget,
                         started=started, timezone=timezone, locale=locale)


def continue_dataset(database, *, company_id: str, dataset_version_id: str,
                     subject_id: str, release_key: str = ENGINE_RELEASE_KEY,
                     chunk_size: int = CHUNK_SIZE,
                     time_budget: float = PREPARE_BUDGET_SECONDS,
                     timezone: str = "America/Bogota",
                     locale: str = "es-CO") -> Preparation:
    """Sigue una preparacion que se quedo en `staging`. Reanudar es idempotente."""
    started = time.monotonic()
    with database.session(company_id=company_id, subject_id=subject_id) as connection:
        dataset = load_dataset(connection, dataset_version_id)
        if dataset is None:
            raise PreparationError("dataset-unknown", "no such dataset version")
        if dataset["state"] != "staging":
            return Preparation(
                dataset_version_id=dataset_version_id, state=dataset["state"],
                movement_count=dataset["movement_count"],
                rejected_count=dataset["rejected_count"],
                record_count=dataset["record_count"], reused=True, rejections=(),
                complete=dataset["state"] != "staging",
                expected_record_count=dataset.get("expected_record_count") or 0)
        context = _preparation_context(
            connection, company_id=company_id, artifact_id=dataset["artifact_id"],
            mapping_version_id=dataset["mapping_version_id"],
            release_key=release_key)
        context["financial_account_id"] = _account_of(
            connection, dataset_version_id, context["data_source_id"])
        expected = dataset.get("expected_record_count") or _count_records(
            connection, context["run_id"], context["mapping"].first_data_row)

    return _drive_chunks(database, company_id=company_id, subject_id=subject_id,
                         dataset_id=dataset_version_id, context=context,
                         expected=expected, chunk_size=chunk_size,
                         time_budget=time_budget, started=started,
                         timezone=timezone, locale=locale)


def _account_of(connection: psycopg.Connection, dataset_version_id: str,
                data_source_id: str) -> str:
    """La cuenta con la que ya se estaba preparando este dataset.

    Reanudar tiene que usar **la misma**: cambiarla a mitad partiria el conjunto
    entre dos cuentas y ninguna de las dos cuadraria.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT financial_account_id FROM fincilia.canonical_movement "
            "WHERE dataset_version_id = %s LIMIT 1", (dataset_version_id,))
        row = cursor.fetchone()
    if row is not None:
        return str(row[0])
    return linked_account(connection, data_source_id=data_source_id)


def _drive_chunks(database, *, company_id: str, subject_id: str, dataset_id: str,
                  context: dict[str, Any], expected: int, chunk_size: int,
                  time_budget: float, started: float, timezone: str,
                  locale: str) -> Preparation:
    """El bucle de lotes. Una transaccion por lote y ni una fila de mas en memoria."""
    rejections: list[dict[str, Any]] = []
    movements = 0
    rejected = 0
    processed = 0

    with database.session(company_id=company_id, subject_id=subject_id) as connection:
        chunk_ordinal, last_record = _resume_point(connection, dataset_id)
        if chunk_ordinal == 0:
            # El sello del artefacto y las decisiones humanas: cardinalidad uno,
            # asi que se escriben una vez y no por lote.
            with connection.cursor() as cursor:
                _seal_artifact(cursor, company_id=company_id,
                               artifact_id=context["artifact_id"],
                               artifact_sha256=context["artifact_sha256"],
                               release=context["release"], run_id=context["run_id"],
                               subject_id=subject_id, dataset_version_id=dataset_id)
                _seal_decisions(cursor, company_id=company_id,
                                decisions=context["decisions"],
                                dataset_version_id=dataset_id,
                                release=context["release"], run_id=context["run_id"],
                                subject_id=subject_id)

    while True:
        if time.monotonic() - started > time_budget:
            # Presupuesto agotado. El dataset se queda en `staging`, que es la
            # respuesta honesta: ni publicado, ni perdido, ni a medias en silencio.
            return _report(database, company_id=company_id, subject_id=subject_id,
                           dataset_id=dataset_id, state="staging",
                           expected=expected, rejections=rejections)

        with database.session(company_id=company_id,
                              subject_id=subject_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT raw_record_id, record_ordinal, raw_values, origin_locator "
                    "FROM fincilia.raw_record WHERE processing_run_id = %s "
                    "AND record_ordinal >= %s AND record_ordinal > %s "
                    "ORDER BY record_ordinal LIMIT %s",
                    (context["run_id"], context["mapping"].first_data_row,
                     last_record, chunk_size))
                rows = cursor.fetchall()
            if not rows:
                break
            accepted, refused, detail = _write_chunk(
                connection, company_id=company_id, dataset_version_id=dataset_id,
                chunk_ordinal=chunk_ordinal, rows=rows,
                mapping=context["mapping"],
                data_source_id=context["data_source_id"],
                financial_account_id=context["financial_account_id"],
                release=context["release"])

        movements += accepted
        rejected += refused
        processed += len(rows)
        # Solo se guardan los primeros rechazos: la cuenta es exacta y la lista es
        # una muestra. Retener cien mil motivos para ensenar cincuenta es la clase
        # de detalle que convierte una respuesta en un volcado de memoria.
        for item in detail:
            if len(rejections) < MAX_REPORTED_REJECTIONS:
                rejections.append(item)
        last_record = int(rows[-1][1])
        chunk_ordinal += 1
        del rows

    return _finalise(database, company_id=company_id, subject_id=subject_id,
                     dataset_id=dataset_id, context=context, expected=expected,
                     rejections=rejections, timezone=timezone, locale=locale)


def _report(database, *, company_id: str, subject_id: str, dataset_id: str,
            state: str, expected: int,
            rejections: list[dict[str, Any]]) -> Preparation:
    """Progreso por conteos, nunca por payload."""
    with database.session(company_id=company_id, subject_id=subject_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT coalesce(sum(movement_count), 0), "
                "       coalesce(sum(rejected_count), 0), "
                "       coalesce(max(last_record), 0), count(*) "
                "FROM fincilia.dataset_chunk WHERE dataset_version_id = %s",
                (dataset_id,))
            movements, rejected, last_record, chunks = cursor.fetchone()
    return Preparation(
        dataset_version_id=dataset_id, state=state, movement_count=int(movements),
        rejected_count=int(rejected), record_count=int(movements) + int(rejected),
        reused=False, rejections=tuple(rejections), complete=state != "staging",
        expected_record_count=expected, chunks=int(chunks),
        last_record=int(last_record))


def _movements_digest(connection: psycopg.Connection, dataset_id: str) -> str:
    """Huella de lo publicado, leida de la base y no de la memoria.

    Se digiere lo que **quedo escrito**, no lo que se pretendia escribir: si un
    lote no entro, la huella cambia y el manifiesto deja de cuadrar, que es
    exactamente lo que un manifiesto sirve para detectar.

    Se recorre con un cursor de servidor: cien mil importes no caben en una lista
    y tampoco hacen falta.
    """
    running = hashlib.sha256()
    name = f"movements_{uuid.uuid4().hex}"
    with connection.cursor(name=name) as cursor:
        cursor.itersize = DIGEST_BATCH
        cursor.execute(
            "SELECT r.record_ordinal, m.amount, m.currency_code, m.direction, "
            "       m.occurred_on, m.field_digests "
            "FROM fincilia.canonical_movement m "
            "JOIN fincilia.source_record s ON s.source_record_id = m.source_record_id "
            "JOIN fincilia.raw_record r ON r.raw_record_id = s.raw_record_id "
            "WHERE m.dataset_version_id = %s ORDER BY r.record_ordinal",
            (dataset_id,))
        for ordinal, amount, currency, direction, occurred_on, digests in cursor:
            running.update(canonical_json({
                "ordinal": int(ordinal), "amount": f"{amount:.12f}",
                "currency": currency, "direction": direction,
                "occurred_on": occurred_on.isoformat(),
                "fields": digests or {},
            }).encode("utf-8"))
    return running.hexdigest()


def _finalise(database, *, company_id: str, subject_id: str, dataset_id: str,
              context: dict[str, Any], expected: int,
              rejections: list[dict[str, Any]], timezone: str,
              locale: str) -> Preparation:
    """El paso que hace visible el conjunto entero, y solo si esta entero.

    Aqui es donde `staging` se convierte en `validated`, en **una** sentencia. No
    hay ventana en la que medio dataset parezca completo: o los conteos cuadran
    con lo esperado, o no se pasa.
    """
    with database.session(company_id=company_id, subject_id=subject_id) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT coalesce(sum(movement_count), 0), "
                "       coalesce(sum(rejected_count), 0), count(*) "
                "FROM fincilia.dataset_chunk WHERE dataset_version_id = %s",
                (dataset_id,))
            movements, rejected, chunks = cursor.fetchone()
        movements, rejected, chunks = int(movements), int(rejected), int(chunks)

        if movements + rejected != expected:
            raise PreparationError(
                "dataset-incomplete",
                f"the chunks account for {movements + rejected} rows and the "
                f"document has {expected}; a dataset that does not add up is not "
                "published")
        if movements == 0:
            raise PreparationError("no-mappable-rows",
                                   "not a single row could be read with this mapping")

        digest = _movements_digest(connection, dataset_id)
        manifest = {
            "canonical_schema_version": context["release"]["canonical_schema_version"],
            "company_id": company_id,
            "deterministic_config": {
                "chunk_size": CHUNK_SIZE,
                "date_format": context["mapping"].date_format,
                "decimal_format": context["mapping"].decimal_format,
                "direction_mode": context["mapping"].direction_mode,
                "first_data_row": context["mapping"].first_data_row,
                "header_row": context["mapping"].header_row,
                "lineage_plan_digest": context["plan"]["digest"],
            },
            "engine_release_key": context["release"]["release_key"],
            "input_artifact_sha256": context["artifact_sha256"],
            "locale": locale,
            "mapping_definition_digest": context["definition_digest"],
            "mapping_version_id": context["mapping_version_id"],
            "random_seed": 0,
            "source_schema_digest": context["source_schema_digest"],
            "timezone": timezone,
        }
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO fincilia.reproducibility_manifest (manifest_id, "
                "company_id, dataset_version_id, engine_release_id, "
                "input_artifact_sha256, mapping_version_id, deterministic_config, "
                "locale, timezone, random_seed, output_digests, reproduction_key) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s::jsonb, %s, %s, "
                "0, %s::jsonb, %s) ON CONFLICT (dataset_version_id) DO NOTHING",
                (company_id, dataset_id, context["release"]["release_id"],
                 context["artifact_sha256"] or "0" * 64,
                 context["mapping_version_id"],
                 dumps_compact(manifest["deterministic_config"]), locale, timezone,
                 dumps_compact({"movements": digest, "count": movements}),
                 reproduction_key(manifest)))
            cursor.execute(
                "UPDATE fincilia.dataset_version SET state = 'validated', "
                "completeness_state = %s, lineage_state = 'complete', "
                "record_count = %s, movement_count = %s, rejected_count = %s, "
                "validated_by = %s, validated_at = now() "
                "WHERE dataset_version_id = %s AND state = 'staging'",
                ("verified" if rejected == 0 else "mismatch", movements + rejected,
                 movements, rejected, subject_id, dataset_id))

    return Preparation(
        dataset_version_id=dataset_id, state="validated", movement_count=movements,
        rejected_count=rejected, record_count=movements + rejected, reused=False,
        rejections=tuple(rejections), complete=True, expected_record_count=expected,
        chunks=chunks, last_record=0)


# --------------------------------------------------------------------------- #
# Publicacion
# --------------------------------------------------------------------------- #

class PublicationError(Exception):
    """La publicacion no procede, y el motivo es del cliente."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def release_state_of(connection: psycopg.Connection,
                     dataset_version_id: str) -> str:
    """Estado actual de la release con la que se preparo un dataset."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT e.state FROM fincilia.dataset_version d "
            "JOIN fincilia.engine_release e ON e.release_id = d.engine_release_id "
            "WHERE d.dataset_version_id = %s", (dataset_version_id,))
        row = cursor.fetchone()
    return str(row[0]) if row else "unknown"


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

    # Entre preparar y publicar pueden pasar dias, y una release puede quedar
    # superseded en medio. Sellar con ella seria firmar lo que ya no vale.
    state = release_state_of(connection, dataset_version_id)
    if state != "approved":
        raise PublicationError(
            "engine-release-not-approved",
            f"the engine release behind this dataset is now {state}; prepare it "
            "again against an approved release")

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


def load_plan_steps(connection: psycopg.Connection,
                    plan_id: str) -> tuple[TransformStep, ...]:
    """Las etapas guardadas de un plan, tal y como se escribieron.

    Se leen de la base y **no** se vuelven a construir del mapeo: reconstruir con
    el codigo de hoy explicaria lo publicado con reglas que no lo produjeron, que
    es el `latest` que el manifiesto prohibe con otro nombre.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT canonical_field, step_ordinal, stage, operation, "
            "       input_semantic_type, output_semantic_type, transform_ref, "
            "       configuration_digest, parser_version, rule_version, source_column "
            "FROM fincilia.lineage_transform_step WHERE plan_id = %s "
            "ORDER BY canonical_field, step_ordinal", (plan_id,))
        return tuple(TransformStep(*row) for row in cursor)


def load_movement(connection: psycopg.Connection,
                  movement_id: str) -> dict[str, Any] | None:
    """Un movimiento con las **seis etapas logicas** de cada campo publicado.

    Esto es lo que hace auditable un importe: no «viene de este fichero», sino
    «los bytes de este sha256, la celda de la fila 42 columna 3 en los bytes 1180
    a 1236, el texto `-1.234,56`, leido como decimal con coma en la etapa
    `transformed_value`, canonizado y publicado con esta huella».

    El camino se **reconstruye**: el plan pone el como y la fila pone el cual. Si
    falta cualquiera de las dos partes, `lineage_complete` sale en falso y lo
    dice, en vez de devolver un camino a medias que parezca entero.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT m.movement_id, m.amount, m.currency_code, m.direction, "
            "       m.description, m.reference_original, m.occurred_on, "
            "       m.posted_on, m.value_date, m.accounting_date, m.state, "
            "       m.kind, r.record_ordinal, m.dataset_version_id, "
            "       r.origin_locator, r.raw_values, a.filename, d.state, "
            "       m.field_digests, d.lineage_plan_id, s.source_record_id, "
            "       r.raw_record_id, e.release_key "
            "FROM fincilia.canonical_movement m "
            "JOIN fincilia.source_record s ON s.source_record_id = m.source_record_id "
            "JOIN fincilia.raw_record r ON r.raw_record_id = s.raw_record_id "
            "JOIN fincilia.source_artifact a ON a.artifact_id = r.artifact_id "
            "JOIN fincilia.dataset_version d "
            "       ON d.dataset_version_id = m.dataset_version_id "
            "JOIN fincilia.engine_release e ON e.release_id = m.engine_release_id "
            "WHERE m.movement_id = %s", (movement_id,))
        row = cursor.fetchone()
        if row is None:
            return None

    payload = _movement_row(row)
    locator = row[14] or {}
    digests = row[18] or {}
    plan_id = str(row[19]) if row[19] else None
    payload.update({
        "dataset_version_id": str(row[13]),
        "dataset_state": row[17],
        "engine_release": row[22],
        "origin": {"filename": row[16], "locator": locator, "values": row[15]},
    })

    if plan_id is None:
        # Publicado antes de que existiera el plan. Decirlo es mas honesto que
        # devolver un camino corto y dejar que parezca el contrato entero.
        payload["lineage"] = []
        payload["lineage_complete"] = False
        payload["lineage_reason"] = (
            "this dataset was published before the transform plan existed and "
            "cannot reconstruct the six stages")
        return payload

    steps = load_plan_steps(connection, plan_id)
    fields = sorted({step.canonical_field for step in steps})
    reconstructed: dict[str, list[dict[str, Any]]] = {}
    problems: list[str] = []
    for field in fields:
        try:
            reconstructed[field] = reconstruct(
                steps, canonical_field=field, origin_locator=locator,
                raw_record_id=str(row[21]), source_record_id=str(row[20]),
                movement_id=movement_id, value_digest=digests.get(field))
        except LineageError as error:
            problems.append(f"{field}: {error}")

    payload["lineage"] = [
        {"field": field, "stages": stages,
         # Lo que la interfaz ensena de un vistazo: donde estaba y como se leyo.
         "cell": stages[1]["identity"]["cell"],
         "transform": stages[3]["transform_ref"],
         "value_digest": stages[5]["identity"]["value_digest"],
         "operation": stages[5]["operation"]}
        for field, stages in sorted(reconstructed.items())]
    payload["lineage_complete"] = not problems and bool(reconstructed)
    if problems:
        payload["lineage_reason"] = "; ".join(problems)
    return payload
