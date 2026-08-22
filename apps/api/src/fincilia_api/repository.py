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
                    findings: list, uploaded_by: str) -> Artifact:
    artifact_id = new_id()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.source_artifact (artifact_id, company_id, filename, "
            "byte_size, content_sha256, media_type, zone, object_key, status, "
            "findings, uploaded_by) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s) "
            f"RETURNING {ARTIFACT_COLUMNS}",
            (artifact_id, company_id, filename, byte_size, content_sha256, media_type,
             zone, object_key, status,
             json.dumps(findings, ensure_ascii=False, sort_keys=True), uploaded_by))
        row = cursor.fetchone()
    return _artifact(row)


def list_artifacts(connection: psycopg.Connection, *, limit: int = 50) -> list[Artifact]:
    bounded = max(1, min(int(limit), 200))
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {ARTIFACT_COLUMNS} FROM fincilia.source_artifact "
            "ORDER BY uploaded_at DESC, artifact_id LIMIT %s", (bounded,))
        return [_artifact(row) for row in cursor.fetchall()]


def enqueue_run(connection: psycopg.Connection, *, company_id: str,
                artifact_id: str, kind: str) -> str | None:
    """Encola un trabajo. `None` si ya habia uno para ese artefacto y tipo.

    La unicidad la pone `uq_run_attempt`, no una comprobacion previa: entre mirar
    y escribir cabe otra peticion.
    """
    run_id = new_id()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.processing_run (run_id, company_id, artifact_id, kind) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (artifact_id, kind, attempt) DO NOTHING RETURNING run_id::text",
            (run_id, company_id, artifact_id, kind))
        row = cursor.fetchone()
        if row is None:
            return None
        # El puntero se escribe en la misma transaccion que el trabajo. Si fueran
        # dos, un fallo entre medias dejaria un trabajo que ningun worker ve.
        cursor.execute(
            "INSERT INTO fincilia.dispatch_pointer (run_id, company_id, kind) "
            "VALUES (%s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
            (row[0], company_id, kind))
    return row[0]


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
