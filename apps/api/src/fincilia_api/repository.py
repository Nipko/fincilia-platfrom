"""Acceso a datos de identidad, autorizacion y auditoria.

Ninguna funcion abre su propia conexion: reciben una que ya viene dentro de una
transaccion con el contexto de tenancy fijado. Asi es imposible escribir aqui una
consulta que se salte RLS por olvidar el alcance, porque el alcance no se decide
en este modulo.

Las consultas nunca interpolan valores en el SQL. El `company_id` que llega del
cliente se compara contra el contexto autorizado antes de llegar hasta aqui.
"""

from __future__ import annotations

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


def list_audit(connection: psycopg.Connection, *, limit: int = 50) -> list[dict]:
    """Ultimos eventos **del alcance ya fijado**; no recibe `company_id`.

    Pasar la empresa por parametro invitaria a filtrar en Python lo que ya filtra
    la politica, y a que alguien la pasara distinta del contexto.
    """
    bounded = max(1, min(int(limit), 200))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT audit_event_id::text, action, resource_kind, resource_ref, "
            "outcome, occurred_at, detail FROM fincilia.audit_event "
            # La politica deja ver dos conjuntos disjuntos: los eventos de esta
            # empresa y los de plataforma del propio sujeto, que no tienen
            # empresa. Un inicio de sesion no pertenece al registro de una
            # empresa, asi que aqui se piden solo los que si.
            "WHERE company_id IS NOT NULL "
            "ORDER BY occurred_at DESC, audit_event_id LIMIT %s", (bounded,))
        rows = cursor.fetchall()
    return [{"audit_event_id": row[0], "action": row[1], "resource_kind": row[2],
             "resource_ref": row[3], "outcome": row[4],
             "occurred_at": row[5].isoformat(), "detail": row[6]} for row in rows]


# --------------------------------------------------------------------------- #
# Artefactos de origen
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    company_id: str
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
                   ("artifact_id", "filename", "byte_size", "content_sha256",
                    "media_type", "zone", "status", "findings", "uploaded_at")}
        return payload


ARTIFACT_COLUMNS = ("artifact_id::text, company_id::text, filename, byte_size, "
                    "content_sha256, media_type, zone, object_key, status, findings, "
                    "uploaded_by::text, uploaded_at")


def _artifact(row) -> Artifact:
    values = list(row)
    values[11] = values[11].isoformat()
    return Artifact(*values)


def find_artifact_by_content(connection: psycopg.Connection,
                             content_sha256: str) -> Artifact | None:
    """Busca por contenido dentro del alcance ya fijado.

    No recibe `company_id`: la politica ya acota la busqueda, y pasarlo invitaria
    a filtrar en Python lo que filtra la base.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {ARTIFACT_COLUMNS} FROM fincilia.source_artifact "
            "WHERE content_sha256 = %s", (content_sha256,))
        row = cursor.fetchone()
    return _artifact(row) if row else None


def insert_artifact(connection: psycopg.Connection, *, company_id: str,
                    filename: str, byte_size: int, content_sha256: str,
                    media_type: str, zone: str, object_key: str, status: str,
                    findings: list, uploaded_by: str) -> tuple[Artifact, bool]:
    """Registra la entrega. Devuelve `(artefacto, si_es_nueva)`.

    La idempotencia la decide la restriccion `uq_artifact_content`, no una
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
            "INSERT INTO fincilia.source_artifact (artifact_id, company_id, filename, "
            "byte_size, content_sha256, media_type, zone, object_key, status, "
            "findings, uploaded_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
            "ON CONFLICT (company_id, content_sha256) DO NOTHING "
            f"RETURNING {ARTIFACT_COLUMNS}",
            (artifact_id, company_id, filename, byte_size, content_sha256, media_type,
             zone, object_key, status,
             json.dumps(findings, ensure_ascii=False, sort_keys=True), uploaded_by))
        row = cursor.fetchone()
    if row is not None:
        return _artifact(row), True

    existing = find_artifact_by_content(connection, content_sha256)
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
