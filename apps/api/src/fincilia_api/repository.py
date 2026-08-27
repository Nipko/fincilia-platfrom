"""Acceso a datos de identidad, autorizacion y auditoria.

Ninguna funcion abre su propia conexion: reciben una que ya viene dentro de una
transaccion con el contexto de tenancy fijado. Asi es imposible escribir aqui una
consulta que se salte RLS por olvidar el alcance, porque el alcance no se decide
en este modulo.

Las consultas nunca interpolan valores en el SQL. El `company_id` que llega del
cliente se compara contra el contexto autorizado antes de llegar hasta aqui.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass

import psycopg

from fincilia_platform.identity import Credential

MAX_AUDIT_DETAIL_BYTES = 4096
UUID_SHAPE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@dataclass(frozen=True)
class Subject:
    subject_id: str
    display_name: str
    status: str

    @property
    def active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True)
class Authorization:
    """Lo que la base dice ahora mismo sobre un sujeto en una empresa."""

    company_id: str
    firm_id: str
    engagement_id: str
    roles: tuple[str, ...]
    version: int
    version_updated_at: int


@dataclass(frozen=True)
class CompanyRow:
    company_id: str
    legal_name: str
    country_code: str
    status: str


def new_id() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Identidad
# --------------------------------------------------------------------------- #

def find_credential(connection: psycopg.Connection, username: str) -> Credential | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subject_id::text, username, algorithm, iterations, salt, secret_hash "
            "FROM fincilia.local_credential WHERE username = %s", (username,))
        row = cursor.fetchone()
    return Credential(*row) if row else None


def load_subject(connection: psycopg.Connection, subject_id: str) -> Subject | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT subject_id::text, display_name, status "
            "FROM fincilia.subject WHERE subject_id = %s", (subject_id,))
        row = cursor.fetchone()
    return Subject(*row) if row else None


# --------------------------------------------------------------------------- #
# Autorizacion
# --------------------------------------------------------------------------- #

def accessible_company_ids(connection: psycopg.Connection,
                           subject_id: str) -> tuple[str, ...]:
    """Empresas donde el sujeto tiene alguna concesion viva.

    Se lee con contexto de **sujeto**, no de empresa: para pedir el contexto de
    una empresa hay que saber antes cuales le corresponden, y ese arranque en
    frio necesita una via propia. La politica de V0002 la abre solo para las
    concesiones cuyo `subject_id` coincide.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT company_id::text FROM fincilia.company_grant "
            "WHERE subject_id = %s AND revoked_at IS NULL ORDER BY 1", (subject_id,))
        return tuple(row[0] for row in cursor.fetchall())


def authorize(connection: psycopg.Connection, subject_id: str,
              company_id: str) -> Authorization | None:
    """Resuelve roles y delegacion. `None` es denegacion, sin matices.

    Hacen falta las tres cosas a la vez: una delegacion activa de la firma sobre
    la empresa, una membresia activa del sujeto en esa firma, y al menos una
    concesion viva. Revocar cualquiera de las tres corta el acceso sin borrar
    ningun hecho financiero.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT e.engagement_id::text, e.firm_id::text "
            "FROM fincilia.engagement e "
            "JOIN fincilia.membership m ON m.firm_id = e.firm_id "
            "WHERE e.company_id = %s AND e.status = 'active' "
            "  AND m.subject_id = %s AND m.status = 'active' "
            "  AND (e.valid_to IS NULL OR e.valid_to >= CURRENT_DATE) "
            "LIMIT 1", (company_id, subject_id))
        delegation = cursor.fetchone()
        if delegation is None:
            return None

        cursor.execute(
            "SELECT company_role FROM fincilia.company_grant "
            "WHERE company_id = %s AND subject_id = %s AND revoked_at IS NULL "
            "ORDER BY company_role", (company_id, subject_id))
        roles = tuple(row[0] for row in cursor.fetchall())
        if not roles:
            return None

        cursor.execute(
            # `floor`, no `::bigint`: el cast redondea, y redondear hacia
            # arriba haria parecer que el cambio ocurrio un segundo despues de
            # lo real, invalidando tokens recien emitidos sin motivo. Al
            # truncar, el unico coste es que un cambio puede tardar hasta un
            # segundo en invalidar un token emitido en ese mismo segundo.
            "SELECT version, floor(extract(epoch FROM updated_at))::bigint "
            "FROM fincilia.authorization_version WHERE company_id = %s", (company_id,))
        version = cursor.fetchone()
    if version is None:
        # Sin fila de version no hay forma de invalidar un token tras revocar.
        # Falta un invariante, no un dato opcional: se deniega.
        return None
    return Authorization(company_id, delegation[1], delegation[0], roles,
                         int(version[0]), int(version[1]))


def bump_authorization_version(connection: psycopg.Connection,
                               company_id: str) -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.authorization_version "
            "SET version = version + 1, updated_at = now() "
            "WHERE company_id = %s RETURNING version", (company_id,))
        row = cursor.fetchone()
    if row is None:
        raise LookupError("company has no authorization version")
    return int(row[0])


# --------------------------------------------------------------------------- #
# Empresas
# --------------------------------------------------------------------------- #

def load_company(connection: psycopg.Connection, company_id: str) -> CompanyRow | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT company_id::text, legal_name, country_code, status "
            "FROM fincilia.company WHERE company_id = %s", (company_id,))
        row = cursor.fetchone()
    return CompanyRow(*row) if row else None


# --------------------------------------------------------------------------- #
# Auditoria
# --------------------------------------------------------------------------- #

def record_audit(connection: psycopg.Connection, *, subject_id: str | None,
                 company_id: str | None, action: str, resource_kind: str,
                 resource_ref: str, outcome: str,
                 detail: dict | None = None) -> str:
    """Escribe un evento. La auditoria es append-only tambien por privilegio.

    `detail` lleva metadatos, nunca contenido: que ocurrio, no que decia el
    fichero ni cuanto valia el movimiento.
    """
    payload = json.dumps(detail or {}, sort_keys=True, ensure_ascii=False)
    if len(payload.encode("utf-8")) > MAX_AUDIT_DETAIL_BYTES:
        raise ValueError("audit detail carries metadata, not payload")
    event_id = new_id()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.audit_event (audit_event_id, company_id, subject_id, "
            "action, resource_kind, resource_ref, outcome, detail) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
            (event_id, company_id, subject_id, action, resource_kind, resource_ref,
             outcome, payload))
    return event_id


def list_audit_page(connection: psycopg.Connection, *, limit: int = 50,
                    action: str | None = None, outcome: str | None = None,
                    resource_kind: str | None = None,
                    before: tuple[object, str] | None = None) -> tuple[list[dict], bool]:
    """Ultimos eventos **del alcance ya fijado**; no recibe `company_id`.

    Pasar la empresa por parametro invitaria a filtrar en Python lo que ya filtra
    la politica, y a que alguien la pasara distinta del contexto.
    """
    bounded = max(1, min(int(limit), 100))
    where = ["event.company_id IS NOT NULL"]
    params: list[object] = []
    if action is not None:
        where.append("event.action = %s")
        params.append(action)
    if outcome is not None:
        where.append("event.outcome = %s")
        params.append(outcome)
    if resource_kind is not None:
        where.append("event.resource_kind = %s")
        params.append(resource_kind)
    if before is not None:
        where.append("(event.occurred_at, event.audit_event_id) < (%s, %s)")
        params.extend(before)
    params.append(bounded + 1)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT event.audit_event_id::text, event.action, "
            "event.resource_kind, event.resource_ref, event.outcome, "
            "event.occurred_at, event.detail, event.subject_id::text, "
            "subject_row.display_name FROM fincilia.audit_event event "
            "LEFT JOIN fincilia.subject subject_row "
            "  ON subject_row.subject_id = event.subject_id "
            # La politica deja ver dos conjuntos disjuntos: los eventos de esta
            # empresa y los de plataforma del propio sujeto, que no tienen
            # empresa. Un inicio de sesion no pertenece al registro de una
            # empresa, asi que aqui se piden solo los que si.
            f"WHERE {' AND '.join(where)} "
            "ORDER BY event.occurred_at DESC, event.audit_event_id DESC LIMIT %s",
            params)
        rows = cursor.fetchall()
    has_more = len(rows) > bounded
    rows = rows[:bounded]
    return ([{"audit_event_id": row[0], "action": row[1], "resource_kind": row[2],
             "resource_ref": row[3], "outcome": row[4],
             "occurred_at": row[5].isoformat(), "detail": row[6],
             "subject_id": row[7], "actor_name": row[8] or "Sistema"}
            for row in rows], has_more)


def list_audit(connection: psycopg.Connection, *, limit: int = 50) -> list[dict]:
    events, _has_more = list_audit_page(connection, limit=limit)
    return events


# --------------------------------------------------------------------------- #
# Artefactos de origen
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    company_id: str
    data_source_id: str | None
    filename: str
    byte_size: int
    content_sha256: str
    media_type: str
    zone: str
    object_key: str
    status: str
    findings: list
    uploaded_by: str
    uploaded_at: str

    def as_dict(self) -> dict:
        payload = {key: getattr(self, key) for key in
                   ("artifact_id", "data_source_id", "filename", "byte_size", "content_sha256",
                    "media_type", "zone", "status", "findings", "uploaded_at")}
        return payload


ARTIFACT_COLUMNS = ("artifact_id::text, company_id::text, data_source_id::text, "
                    "filename, byte_size, "
                    "content_sha256, media_type, zone, object_key, status, findings, "
                    "uploaded_by::text, uploaded_at")


def _artifact(row) -> Artifact:
    values = list(row)
    values[12] = values[12].isoformat()
    return Artifact(*values)


def find_artifact_by_content(connection: psycopg.Connection,
                             data_source_id: str,
                             content_sha256: str) -> Artifact | None:
    """Busca por contenido dentro del alcance ya fijado.

    No recibe `company_id`: la politica ya acota la busqueda, y pasarlo invitaria
    a filtrar en Python lo que filtra la base.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {ARTIFACT_COLUMNS} FROM fincilia.source_artifact "
            "WHERE data_source_id = %s AND content_sha256 = %s",
            (data_source_id, content_sha256))
        row = cursor.fetchone()
    return _artifact(row) if row else None


def insert_artifact(connection: psycopg.Connection, *, company_id: str,
                    data_source_id: str, filename: str, byte_size: int,
                    content_sha256: str,
                    media_type: str, zone: str, object_key: str, status: str,
                    findings: list, uploaded_by: str) -> tuple[Artifact, bool]:
    """Registra la entrega. Devuelve `(artefacto, si_es_nueva)`.

    La idempotencia la decide el indice `uq_artifact_source_content`, no una
    comprobacion previa. Entre mirar «¿ya existe?» y escribir cabe otra peticion,
    y con dos subidas simultaneas de los mismos bytes esa ventana producia o dos
    filas o un 500 por violacion de unicidad. Aqui el perdedor no falla: lee la
    fila del ganador y responde lo mismo que el.

    Requiere READ COMMITTED, que es lo que `Database` fija explicitamente: bajo
    REPEATABLE READ el `SELECT` de respaldo no veria la fila recien confirmada y
    la API reportaria un fallo por una entrega que si existe.
    """
    artifact_id = new_id()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.source_artifact (artifact_id, company_id, "
            "data_source_id, filename, byte_size, content_sha256, media_type, "
            "zone, object_key, status, "
            "findings, uploaded_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
            "ON CONFLICT (company_id, data_source_id, content_sha256) "
            "WHERE data_source_id IS NOT NULL DO NOTHING "
            f"RETURNING {ARTIFACT_COLUMNS}",
            (artifact_id, company_id, data_source_id, filename, byte_size,
             content_sha256, media_type, zone, object_key, status,
             json.dumps(findings, ensure_ascii=False, sort_keys=True), uploaded_by))
        row = cursor.fetchone()
    if row is not None:
        return _artifact(row), True

    existing = find_artifact_by_content(connection, data_source_id, content_sha256)
    if existing is None:
        # El conflicto existe pero la fila no se ve bajo la politica. Reportarlo
        # como exito seria afirmar algo que no se puede comprobar.
        raise LookupError("a conflicting artifact is not visible in this context")
    return existing, False


def list_artifacts(connection: psycopg.Connection, *, limit: int = 50) -> list[Artifact]:
    bounded = max(1, min(int(limit), 200))
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {ARTIFACT_COLUMNS} FROM fincilia.source_artifact "
            "ORDER BY uploaded_at DESC, artifact_id LIMIT %s", (bounded,))
        return [_artifact(row) for row in cursor.fetchall()]


def list_artifact_history(
        connection: psycopg.Connection, *, limit: int,
        data_source_id: str | None = None, zone: str = "all",
        processing_status: str = "all", filename: str | None = None,
        cursor: tuple[dt.datetime, str] | None = None,
        direction: str = "next") -> tuple[list[dict], bool, dict]:
    """Historico operativo company-scoped sin valores del documento.

    El orden total `(uploaded_at, artifact_id)` hace estable la paginacion aun
    cuando varias recepciones compartan timestamp. Los laterales seleccionan una
    sola decision, trabajo y version; nunca multiplican el artefacto.
    """
    bounded = max(1, min(int(limit), 100))
    joins = """
FROM fincilia.source_artifact artifact
LEFT JOIN fincilia.data_source source
  ON source.data_source_id = artifact.data_source_id
LEFT JOIN LATERAL (
  SELECT decision, reason_code
  FROM fincilia.promotion_decision promotion_row
  WHERE promotion_row.artifact_id = artifact.artifact_id
  ORDER BY decided_at DESC, decision_id DESC LIMIT 1
) promotion ON true
LEFT JOIN LATERAL (
  SELECT kind, status, error_code
  FROM fincilia.processing_run run_row
  WHERE run_row.artifact_id = artifact.artifact_id
  ORDER BY queued_at DESC, run_id DESC LIMIT 1
) latest_run ON true
LEFT JOIN LATERAL (
  SELECT dataset_version_id, state, completeness_state, record_count,
         movement_count, rejected_count
  FROM fincilia.dataset_version dataset_row
  WHERE dataset_row.artifact_id = artifact.artifact_id
  ORDER BY prepared_at DESC, dataset_version_id DESC LIMIT 1
) latest_dataset ON true
"""
    where = ["true"]
    params: list[object] = []
    if data_source_id is not None:
        where.append("artifact.data_source_id = %s")
        params.append(data_source_id)
    if zone == "raw":
        where.append("promotion.decision = 'promoted'")
    elif zone == "quarantine":
        where.append("promotion.decision IS DISTINCT FROM 'promoted'")
    if processing_status != "all":
        if processing_status == "not_started":
            where.append("latest_run.status IS NULL")
        else:
            where.append("latest_run.status = %s")
            params.append(processing_status)
    if filename:
        escaped = filename.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("artifact.filename ILIKE %s ESCAPE '\\'")
        params.append(f"%{escaped}%")
    filters = "WHERE " + " AND ".join(where)

    summary_sql = f"""
SELECT count(*),
       count(*) FILTER (WHERE promotion.decision = 'promoted'),
       count(*) FILTER (WHERE promotion.decision IS DISTINCT FROM 'promoted'),
       count(*) FILTER (WHERE latest_run.status = 'failed'),
       count(*) FILTER (WHERE artifact.data_source_id IS NULL)
{joins}{filters}
"""
    with connection.cursor() as db_cursor:
        db_cursor.execute(summary_sql, tuple(params))
        summary_row = db_cursor.fetchone() or (0, 0, 0, 0, 0)

    page_where = list(where)
    page_params = list(params)
    ascending = direction == "previous"
    if cursor is not None:
        operator = ">" if ascending else "<"
        page_where.append(
            f"(artifact.uploaded_at, artifact.artifact_id) {operator} "
            "(%s::timestamptz, %s::uuid)")
        page_params.extend(cursor)
    order = "ASC" if ascending else "DESC"
    page_sql = f"""
SELECT artifact.artifact_id::text, artifact.data_source_id::text,
       artifact.filename, artifact.byte_size, artifact.content_sha256,
       artifact.media_type, artifact.status, artifact.uploaded_at,
       source.display_name,
       CASE WHEN promotion.decision = 'promoted' THEN 'raw' ELSE 'quarantine' END,
       promotion.reason_code,
       latest_run.kind, coalesce(latest_run.status, 'not_started'),
       latest_run.error_code,
       latest_dataset.dataset_version_id::text, latest_dataset.state,
       latest_dataset.completeness_state, latest_dataset.record_count,
       latest_dataset.movement_count, latest_dataset.rejected_count
{joins}WHERE {' AND '.join(page_where)}
ORDER BY artifact.uploaded_at {order}, artifact.artifact_id {order}
LIMIT %s
"""
    page_params.append(bounded + 1)
    with connection.cursor() as db_cursor:
        db_cursor.execute(page_sql, tuple(page_params))
        rows = db_cursor.fetchall()
    has_more = len(rows) > bounded
    rows = rows[:bounded]
    if ascending:
        rows.reverse()
    items = [{
        "artifact_id": row[0], "data_source_id": row[1],
        "filename": row[2], "byte_size": row[3],
        "content_sha256": row[4], "media_type": row[5],
        "status": row[6], "uploaded_at": row[7].isoformat(),
        "source_name": row[8] or "Fuente historica no registrada",
        "zone": row[9], "promotion_reason": row[10],
        "latest_run_kind": row[11], "processing_status": row[12],
        "processing_error": row[13], "dataset_version_id": row[14],
        "dataset_state": row[15], "completeness_state": row[16],
        "record_count": row[17], "movement_count": row[18],
        "rejected_count": row[19],
    } for row in rows]
    summary = {
        "total": int(summary_row[0]), "raw": int(summary_row[1]),
        "quarantine": int(summary_row[2]), "failed": int(summary_row[3]),
        "legacy_unattributed": int(summary_row[4]),
    }
    return items, has_more, summary


def enqueue_run(connection: psycopg.Connection, *, company_id: str,
                artifact_id: str, kind: str, issued_context_id: str) -> str:
    """Encola un trabajo a traves de la funcion de despacho.

    La API **no tiene ningun privilegio** sobre `fincilia.dispatch_pointer`: la
    tabla es global y sin RLS, y darle INSERT libre seria darle la capacidad de
    escribir en la cola de cualquier empresa. La funcion valida que la empresa
    coincida con el contexto autorizado, que el artefacto sea visible bajo la
    politica, y escribe trabajo y puntero en la misma transaccion.

    Devuelve el `run_id`, que puede ser el de un trabajo que ya estaba vivo: dos
    subidas de la misma evidencia son una sola entrega y un solo trabajo.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT fincilia.enqueue_processing_run(%s, %s, %s, %s)::text",
            (company_id, artifact_id, kind, issued_context_id))
        row = cursor.fetchone()
    return row[0] if row else ""


def list_runs(connection: psycopg.Connection, artifact_id: str) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT run_id::text, kind, status, attempt, queued_at, finished_at, "
            "result, error_code FROM fincilia.processing_run "
            "WHERE artifact_id = %s ORDER BY queued_at", (artifact_id,))
        rows = cursor.fetchall()
    return [{"run_id": row[0], "kind": row[1], "status": row[2], "attempt": row[3],
             "queued_at": row[4].isoformat(),
             "finished_at": row[5].isoformat() if row[5] else None,
             "result": row[6], "error_code": row[7]} for row in rows]


def spreadsheet_workspace(connection: psycopg.Connection,
                          artifact_id: str) -> dict | None:
    """Inventario sin valores y seleccion vigente del artefacto visible."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT run.result FROM fincilia.processing_run run "
            "WHERE run.artifact_id = %s AND run.kind = 'scan' "
            "  AND run.status = 'succeeded' AND run.result ? 'workbook' "
            "ORDER BY run.finished_at DESC, run.run_id DESC LIMIT 1",
            (artifact_id,))
        scan = cursor.fetchone()
        if scan is None:
            return None
        cursor.execute(
            "SELECT selection_id::text, workbook_identity, sheet_identity, "
            "sheet_name, sheet_ordinal, selected_by::text, selected_at "
            "FROM fincilia.spreadsheet_selection WHERE artifact_id = %s",
            (artifact_id,))
        selected = cursor.fetchone()
    result = scan[0] or {}
    workspace = dict(result.get("workbook") or {})
    workspace["requires_selection"] = bool(result.get("requires_selection"))
    workspace["selection"] = None if selected is None else {
        "selection_id": selected[0], "workbook_identity": selected[1],
        "sheet_identity": selected[2], "sheet_name": selected[3],
        "sheet_ordinal": selected[4], "selected_by": selected[5],
        "selected_at": selected[6].isoformat(),
    }
    return workspace


def select_spreadsheet_sheet(
        connection: psycopg.Connection, *, company_id: str, artifact_id: str,
        workbook_identity: str, sheet_identity: str, sheet_name: str,
        sheet_ordinal: int, selected_by: str) -> tuple[dict, bool]:
    """Fija una hoja una sola vez; replay exacto es inocuo, drift es conflicto."""
    selection_id = new_id()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.spreadsheet_selection (selection_id, company_id, "
            "artifact_id, workbook_identity, sheet_identity, sheet_name, "
            "sheet_ordinal, selected_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (artifact_id) DO NOTHING RETURNING selection_id::text, "
            "workbook_identity, sheet_identity, sheet_name, sheet_ordinal, "
            "selected_by::text, selected_at",
            (selection_id, company_id, artifact_id, workbook_identity,
             sheet_identity, sheet_name, sheet_ordinal, selected_by))
        row = cursor.fetchone()
        created = row is not None
        if row is None:
            cursor.execute(
                "SELECT selection_id::text, workbook_identity, sheet_identity, "
                "sheet_name, sheet_ordinal, selected_by::text, selected_at "
                "FROM fincilia.spreadsheet_selection WHERE artifact_id = %s",
                (artifact_id,))
            row = cursor.fetchone()
    if row is None:
        raise LookupError("the spreadsheet selection is not visible")
    selected = {
        "selection_id": row[0], "workbook_identity": row[1],
        "sheet_identity": row[2], "sheet_name": row[3],
        "sheet_ordinal": row[4], "selected_by": row[5],
        "selected_at": row[6].isoformat(),
    }
    if (selected["workbook_identity"] != workbook_identity
            or selected["sheet_identity"] != sheet_identity
            or selected["sheet_name"] != sheet_name
            or selected["sheet_ordinal"] != sheet_ordinal):
        raise ValueError("spreadsheet-selection-conflict")
    return selected, created


def find_artifact_by_id(connection: psycopg.Connection,
                        artifact_id: str) -> Artifact | None:
    if not UUID_SHAPE.match(artifact_id or ""):
        # Un identificador con otra forma no llega a la base: `uuid = texto` es
        # un error de tipo, y un 500 diria que la cadena viajo mas lejos de lo
        # que deberia.
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {ARTIFACT_COLUMNS} FROM fincilia.source_artifact "
            "WHERE artifact_id = %s", (artifact_id,))
        row = cursor.fetchone()
    return _artifact(row) if row else None


# --------------------------------------------------------------------------- #
# Decisiones de promocion
# --------------------------------------------------------------------------- #

DECISION_COLUMNS = ("decision, reason_code, scanner_release, media_type, "
                    "internal_type, findings, raw_object_key, decided_at")


def latest_decision(connection: psycopg.Connection, artifact_id: str) -> dict | None:
    """Ultima decision de promocion de un artefacto, dentro del alcance fijado."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {DECISION_COLUMNS} FROM fincilia.promotion_decision "
            "WHERE artifact_id = %s ORDER BY decided_at DESC LIMIT 1", (artifact_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    return {"decision": row[0], "reason_code": row[1], "scanner_release": row[2],
            "media_type": row[3], "internal_type": row[4], "findings": row[5],
            "raw_object_key": row[6], "decided_at": row[7].isoformat()}


def decisions_for(connection: psycopg.Connection,
                  artifact_ids: list[str]) -> dict[str, dict]:
    """Decisiones de varios artefactos en una consulta, no una por fila."""
    if not artifact_ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT DISTINCT ON (artifact_id) artifact_id::text, decision, reason_code, "
            "raw_object_key FROM fincilia.promotion_decision "
            "WHERE artifact_id = ANY(%s) ORDER BY artifact_id, decided_at DESC",
            (artifact_ids,))
        rows = cursor.fetchall()
    return {row[0]: {"decision": row[1], "reason_code": row[2],
                     "raw_object_key": row[3]} for row in rows}


def effective_zone(decision: dict | None) -> str:
    """Donde vive la evidencia ahora.

    Sin decision, sigue en cuarentena. Es lo correcto y ademas es lo seguro: si
    una consulta fallara, el resultado seria tratar el fichero como no
    inspeccionado, nunca al reves.
    """
    return "raw" if decision and decision.get("decision") == "promoted" else "quarantine"
