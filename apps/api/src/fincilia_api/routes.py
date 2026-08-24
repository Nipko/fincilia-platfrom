"""Endpoints de identidad, empresas y auditoria.

Un principio recorre el fichero: **el cliente propone, el servidor decide**. El
`company_id` de la ruta se compara contra lo que la base autoriza, y toda lectura
ocurre dentro de una transaccion cuyo alcance ya esta fijado. Filtrar en Python
lo que deberia filtrar la politica es como se construyen las fugas que ninguna
prueba de caso feliz encuentra.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import time

import psycopg

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from fincilia_contracts.ingestion import MAX_UPLOAD_BYTES, RejectedUpload, admit
from fincilia_contracts.tenancy import TenantContext
from fincilia_platform.identity import AuthenticationError
from fincilia_platform.objects import ObjectStoreError, object_key
from fincilia_platform.tokens import issue

from . import datasets, exports, onboarding, reconciliation, repository
from .security import (Principal, ProblemError, company_context, current_principal,
                       forbidden, require, unauthorized)
from fincilia_contracts.errors import problem

logger = logging.getLogger("fincilia.api.routes")

router = APIRouter(prefix="/api/v1")


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=120)
    secret: str = Field(min_length=1, max_length=512)


class SessionResponse(BaseModel):
    token: str
    expires_at: int
    subject_id: str
    display_name: str


class CompanySummary(BaseModel):
    company_id: str
    legal_name: str
    country_code: str
    status: str
    roles: list[str]


class CompanyDetail(CompanySummary):
    firm_id: str
    engagement_id: str | None
    authorization_version: int
    permissions: list[str]


class AuditEvent(BaseModel):
    audit_event_id: str
    action: str
    resource_kind: str
    resource_ref: str
    outcome: str
    occurred_at: str
    detail: dict


class MatchProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left_dataset_id: str = Field(min_length=36, max_length=36)
    right_dataset_id: str = Field(min_length=36, max_length=36)
    left_movement_id: str = Field(min_length=36, max_length=36)
    right_movement_id: str = Field(min_length=36, max_length=36)
    max_days: int = Field(default=3, ge=0, le=31)


class MatchDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: str
    reason_code: str = Field(min_length=3, max_length=80)


class ArtifactSummary(BaseModel):
    artifact_id: str
    filename: str
    byte_size: int
    content_sha256: str
    media_type: str
    # `zone` es donde vive la evidencia **ahora**: `quarantine` mientras no haya
    # una decision de promocion, `raw` cuando la hay. La fila del artefacto no
    # cambia nunca; lo que cambia es si existe una decision.
    zone: str
    status: str
    findings: list[dict]
    uploaded_at: str
    already_present: bool = False
    promotion: dict | None = None


class ArtifactDetail(ArtifactSummary):
    runs: list[dict]


def principal_dependency(request: Request) -> Principal:
    return current_principal(request)


@router.post("/auth/session", response_model=SessionResponse, tags=["identity"])
def open_session(request: Request, body: SessionRequest) -> SessionResponse:
    settings = request.app.state.settings
    database = request.app.state.database
    provider = request.app.state.identity_provider
    throttle = request.app.state.throttle

    if throttle.exhausted(body.username):
        raise ProblemError(problem(
            "too-many-attempts", "Too many attempts", 429,
            "too many sign-in attempts; try again later"))

    try:
        identity = provider.authenticate(body.username, body.secret)
    except AuthenticationError:
        throttle.record_failure(body.username)
        # No se registra el usuario intentado: un evento de auditoria de un
        # intento fallido con nombre convierte la auditoria en un censo de
        # cuentas probadas. Se cuenta el hecho, no el nombre.
        logger.warning("failed sign-in attempt")
        raise unauthorized("invalid credentials") from None

    throttle.clear(body.username)
    now = int(time.time())
    token = issue(identity.subject_id, key=settings.auth_signing_key,
                  issuer=settings.auth_issuer, audience=settings.auth_audience,
                  issued_at=now, ttl_seconds=settings.auth_token_ttl_seconds)

    with database.session(subject_id=identity.subject_id) as connection:
        subject = repository.load_subject(connection, identity.subject_id)
        if subject is None or not subject.active:
            raise unauthorized("invalid credentials")
        repository.record_audit(
            connection, subject_id=identity.subject_id, company_id=None,
            action="auth.session.open", resource_kind="session",
            resource_ref=identity.issuer, outcome="allowed",
            detail={"issuer": identity.issuer})
    return SessionResponse(token=token, expires_at=now + settings.auth_token_ttl_seconds,
                           subject_id=subject.subject_id,
                           display_name=subject.display_name)


def _my_companies(request: Request, principal: Principal) -> list[CompanySummary]:
    """Empresas del sujeto, una sesion por empresa.

    Podria resolverse en una consulta si la politica de `company` abriera por
    sujeto, pero eso obligaria a una politica que consulta otra tabla con RLS y a
    razonar sobre recursion de politicas. Con dos empresas de demo el coste es
    irrelevante y el aislamiento se lee de un vistazo.
    """
    database = request.app.state.database
    with database.session(subject_id=principal.subject_id) as connection:
        candidates = repository.accessible_company_ids(connection, principal.subject_id)

    summaries: list[CompanySummary] = []
    for company_id in candidates:
        try:
            context = company_context(request, principal, company_id)
        except ProblemError:
            # Una concesion viva sobre una empresa cuya delegacion se revoco no
            # da acceso. Se omite en silencio: ya quedo auditada la denegacion.
            continue
        with database.session(company_id=company_id,
                              subject_id=principal.subject_id) as connection:
            company = repository.load_company(connection, company_id)
        if company is None:
            continue
        summaries.append(CompanySummary(
            company_id=company.company_id, legal_name=company.legal_name,
            country_code=company.country_code, status=company.status,
            roles=list(context.roles)))
    return summaries


@router.get("/me", tags=["identity"])
def me(request: Request,
             principal: Principal = Depends(principal_dependency)) -> dict:
    companies = _my_companies(request, principal)
    return {
        "subject_id": principal.subject_id,
        "display_name": principal.display_name,
        "session_expires_at": principal.claims.expires_at,
        "companies": [item.model_dump() for item in companies],
    }


@router.get("/companies", response_model=list[CompanySummary], tags=["companies"])
def list_companies(request: Request,
                         principal: Principal = Depends(principal_dependency),
                         ) -> list[CompanySummary]:
    return _my_companies(request, principal)


@router.get("/companies/{company_id}", response_model=CompanyDetail,
            tags=["companies"])
def read_company(request: Request, company_id: str,
                       principal: Principal = Depends(principal_dependency),
                       ) -> CompanyDetail:
    context = company_context(request, principal, company_id)
    require(context, "company.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        company = repository.load_company(connection, context.company_id)
        if company is None:
            # La autorizacion dijo que si y la politica no devolvio fila: eso es
            # una incoherencia del servidor, no una pista para el cliente.
            logger.error("authorised company is invisible under its own policy")
            raise forbidden()
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="company.read",
            resource_kind="company", resource_ref=context.company_id,
            outcome="allowed", detail={"roles": list(context.roles)})
    return CompanyDetail(
        company_id=company.company_id, legal_name=company.legal_name,
        country_code=company.country_code, status=company.status,
        roles=list(context.roles), firm_id=context.firm_id,
        engagement_id=context.engagement_id,
        authorization_version=context.authorization_version,
        permissions=sorted(context.permissions))


@router.get("/companies/{company_id}/audit", response_model=list[AuditEvent],
            tags=["audit"])
def read_audit(request: Request, company_id: str, limit: int = 50,
                     principal: Principal = Depends(principal_dependency),
                     ) -> list[AuditEvent]:
    context: TenantContext = company_context(request, principal, company_id)
    require(context, "audit.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        events = repository.list_audit(connection, limit=limit)
    return [AuditEvent(**event) for event in events]


# --------------------------------------------------------------------------- #
# Documentos
# --------------------------------------------------------------------------- #

def _read_bounded(upload: UploadFile) -> bytes:
    """Lee con techo. Se corta **mientras** se lee, no despues.

    Comprobar el tamano al final es comprobarlo cuando el fichero ya esta entero
    en memoria: quien quiera tumbar el proceso solo tiene que mandar algo enorme.

    Se lee del fichero temporal directamente, sin `await`, porque este manejador
    corre en un hilo y no en el bucle de eventos.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise ProblemError(problem(
                "file-too-large", "File too large", 413,
                f"the upload exceeds the {MAX_UPLOAD_BYTES} byte ceiling"))
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/companies/{company_id}/documents", response_model=ArtifactSummary,
             tags=["documents"])
def upload_document(request: Request, company_id: str,
                          file: UploadFile = File(...),
                          principal: Principal = Depends(principal_dependency),
                          ) -> ArtifactSummary:
    context = company_context(request, principal, company_id)
    require(context, "document.upload")
    database = request.app.state.database
    store = request.app.state.object_store

    payload = _read_bounded(file)
    filename = (file.filename or "sin-nombre").strip()[:255]
    fingerprint = hashlib.sha256(payload).hexdigest()

    rejection: str | None = None
    try:
        admission = admit(payload, filename)
    except RejectedUpload as error:
        rejection = str(error)
    if rejection is not None:
        with database.session(company_id=context.company_id,
                              subject_id=principal.subject_id) as connection:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="document.upload",
                resource_kind="document", resource_ref=fingerprint,
                outcome="denied", detail={"reason": rejection})
        # Lo rechazado no se guarda: no llego a ser evidencia de nada, y
        # conservarlo solo anadiria superficie que alguien tendria que custodiar.
        raise ProblemError(problem(
            "unsupported-document", "Document not accepted", 415, rejection))

    key = object_key(context.company_id, admission.content_sha256)
    try:
        stored = store.put(
            admission.zone, key, payload, content_type=admission.media_type,
            metadata={"company": context.company_id,
                      "sha256": admission.content_sha256})
    except ObjectStoreError as error:
        logger.error("object store refused the upload: %s", error)
        with database.session(company_id=context.company_id,
                              subject_id=principal.subject_id) as connection:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="document.upload",
                resource_kind="document", resource_ref=fingerprint,
                outcome="error", detail={"reason": "storage_unavailable"})
        # Nada se encola ni se publica: si el almacen fallo, no hay evidencia que
        # procesar, y declararlo exitoso seria ocultar una inconsistencia.
        raise ProblemError(problem(
            "storage-unavailable", "Storage unavailable", 503,
            "the evidence store did not accept the file")) from None

    # La subida no promueve: `admit` devuelve siempre `quarantine`.
    status = "quarantined"
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        # La idempotencia la decide la restriccion, no una comprobacion previa.
        # Dos subidas simultaneas de los mismos bytes son una sola entrega: el
        # perdedor lee la fila del ganador y responde lo mismo, sin fallar.
        artifact, created = repository.insert_artifact(
            connection, company_id=context.company_id, filename=filename,
            byte_size=admission.byte_size, content_sha256=admission.content_sha256,
            media_type=admission.media_type, zone=admission.zone,
            object_key=stored.key, status=status,
            findings=[item.as_dict() for item in admission.findings],
            uploaded_by=principal.subject_id)
        if created:
            # Lo que se encola es el **escaneo**, no el perfilado. Perfilar es
            # leer el fichero entero, y eso no se hace sobre algo que todavia no
            # ha pasado inspeccion: el perfilado lo encola el escaneo si decide
            # promover.
            repository.enqueue_run(connection, company_id=context.company_id,
                                   artifact_id=artifact.artifact_id, kind="scan")
        # La auditoria distingue una entrega nueva de una repetida. Contarlas
        # igual haria imposible saber si alguien reintenta o si algo se duplica.
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="document.upload",
            resource_kind="document", resource_ref=artifact.artifact_id,
            outcome="allowed",
            detail={"result": "created" if created else "duplicate",
                    "zone": admission.zone, "media_type": admission.media_type,
                    "findings": len(admission.findings)})
    return ArtifactSummary(**artifact.as_dict(), already_present=not created)


@router.get("/companies/{company_id}/documents", response_model=list[ArtifactSummary],
            tags=["documents"])
def list_documents(request: Request, company_id: str, limit: int = 50,
                         principal: Principal = Depends(principal_dependency),
                         ) -> list[ArtifactSummary]:
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        artifacts = repository.list_artifacts(connection, limit=limit)
        decisions = repository.decisions_for(
            connection, [item.artifact_id for item in artifacts])
    summaries = []
    for item in artifacts:
        payload = item.as_dict()
        decision = decisions.get(item.artifact_id)
        payload["zone"] = repository.effective_zone(decision)
        summaries.append(ArtifactSummary(**payload, promotion=decision))
    return summaries


@router.get("/companies/{company_id}/documents/{artifact_id}",
            response_model=ArtifactDetail, tags=["documents"])
def read_document(request: Request, company_id: str, artifact_id: str,
                        principal: Principal = Depends(principal_dependency),
                        ) -> ArtifactDetail:
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        artifact = repository.find_artifact_by_id(connection, artifact_id)
        if artifact is None:
            # Ni 404 ni mensaje distinto: un codigo que separa «no existe» de «no
            # puedes» convierte la API en un buscador de documentos ajenos.
            raise forbidden()
        runs = repository.list_runs(connection, artifact_id)
        decision = repository.latest_decision(connection, artifact_id)
    payload = artifact.as_dict()
    # La zona que se publica es la efectiva, no la de la fila: el artefacto es
    # inmutable y siempre dice `quarantine`; quien decide donde vive la evidencia
    # es la decision de promocion.
    payload["zone"] = repository.effective_zone(decision)
    return ArtifactDetail(**payload, runs=runs, promotion=decision)


# --------------------------------------------------------------------------- #
# Mapeo, dataset canonico y movimientos (FNC-P3)
# --------------------------------------------------------------------------- #

class PreviewCell(BaseModel):
    record_ordinal: int
    values: list[str]
    locator: dict


class PreviewPage(BaseModel):
    artifact_id: str
    run_id: str
    header: list[str]
    header_row: int
    first_data_row: int
    columns: list[dict]
    total_records: int
    offset: int
    limit: int
    truncated: bool
    truncation_reason: str | None = None
    rows: list[PreviewCell]


class MappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    data_source_id: str
    display_name: str = Field(min_length=1, max_length=160)
    columns: dict[str, int]
    date_format: str = "iso"
    decimal_format: str = "dot"
    currency: str = Field(min_length=3, max_length=3)
    direction_mode: str = "signed_amount"
    header_row: int = Field(default=1, ge=1)
    first_data_row: int = Field(default=2, ge=1)
    ignored_columns: list[int] = Field(default_factory=list)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambiguity_kind: str
    subject_ref: str = Field(min_length=1, max_length=120)
    resolved_value: str = Field(min_length=1, max_length=64)
    rationale: str = Field(min_length=1, max_length=500)


class DatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    mapping_version_id: str
    financial_account_id: str


class RejectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=200)


class OverrideRequest(BaseModel):
    """Lo que hace falta para decir que una fila no siguio el plan.

    Las dos huellas son obligatorias: sin la del original no se puede comprobar
    que el override describe **este** caso, y no otro que se le parece.
    """

    model_config = ConfigDict(extra="forbid")

    source_record_id: str = Field(min_length=1, max_length=64)
    field_name: str = Field(min_length=1, max_length=64)
    override_kind: str = Field(min_length=1, max_length=32)
    base_step_ordinal: int = Field(ge=1, le=6)
    original_value_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    resulting_value_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    reason_code: str = Field(min_length=1, max_length=64)


def _artifact_or_forbidden(connection, artifact_id: str):
    """El artefacto, o una denegacion indistinguible de «no existe».

    Un codigo que separa «no existe» de «no puedes» convierte la API en un
    buscador de documentos ajenos, y eso vale para toda esta seccion igual que
    para la de documentos.
    """
    try:
        artifact = repository.find_artifact_by_id(connection, artifact_id)
    except psycopg.errors.InvalidTextRepresentation:
        raise forbidden() from None
    if artifact is None:
        raise forbidden()
    return artifact


def _source_or_forbidden(connection, data_source_id: str):
    """Resuelve una fuente dentro del contexto RLS sin permitir enumerarla."""
    try:
        source = onboarding.load_source(connection, data_source_id)
    except psycopg.errors.InvalidTextRepresentation:
        raise forbidden() from None
    if source is None:
        raise forbidden()
    return source


def _preparation_problem(error: datasets.PreparationError) -> ProblemError:
    payload = problem(error.code, "The dataset cannot be prepared", 422, error.detail,
                      blockers=error.blockers)
    return ProblemError(payload)


@router.get("/companies/{company_id}/documents/{artifact_id}/preview",
            response_model=PreviewPage, tags=["mapping"])
def read_preview(request: Request, company_id: str, artifact_id: str,
                 offset: int = 0, limit: int = datasets.DEFAULT_PREVIEW_LIMIT,
                 principal: Principal = Depends(principal_dependency)) -> PreviewPage:
    """La unica lectura del producto que devuelve el contenido del fichero.

    Va por su propio endpoint y pide `dataset.map`, que es mas estricto que el
    `document.read` del perfil estadistico: el perfil dice como es el fichero y
    esto dice que pone en el.

    El evento de auditoria registra quien miro, que documento y cuantas filas.
    **Ni un valor**: el rastro de una lectura no puede ser una copia de lo leido.
    """
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        _artifact_or_forbidden(connection, artifact_id)
        run = datasets.latest_run(connection, artifact_id, "extract")
        if run is None:
            # Solo se extrae lo promovido. Un documento en cuarentena no tiene
            # vista previa, y decir por que es parte del producto.
            raise ProblemError(problem(
                "not-extracted", "No preview available", 409,
                "this document has no completed extraction; evidence still in "
                "quarantine is never extracted"))
        total = datasets.count_records(connection, run["run_id"])
        rows = datasets.preview_records(connection, run["run_id"],
                                        offset=offset, limit=limit)
        profile_run = datasets.latest_run(connection, artifact_id, "profile")
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="document.preview",
            resource_kind="document", resource_ref=artifact_id, outcome="allowed",
            detail={"rows": len(rows), "offset": max(0, int(offset))})

    summary = run["result"] or {}
    profile = (profile_run or {}).get("result") or {}
    return PreviewPage(
        artifact_id=artifact_id, run_id=run["run_id"],
        header=[str(item) for item in (summary.get("header") or [])],
        header_row=int(summary.get("header_row", 1)),
        first_data_row=int(summary.get("first_data_row", 2)),
        # El tipo inferido y su confianza salen del perfil, que es quien mide.
        columns=list(profile.get("columns") or []),
        total_records=total, offset=max(0, int(offset)),
        limit=datasets.effective_limit(limit),
        truncated=bool(summary.get("truncated")),
        truncation_reason=summary.get("truncation_reason"),
        rows=[PreviewCell(record_ordinal=item["record_ordinal"],
                          values=[str(value) for value in item["values"]],
                          locator=item["locator"]) for item in rows])


@router.post("/companies/{company_id}/mappings", tags=["mapping"], status_code=201)
def create_mapping(request: Request, company_id: str, body: MappingRequest,
                   principal: Principal = Depends(principal_dependency)) -> dict:
    """Crea una version de mapeo en borrador y devuelve lo que la bloquea."""
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    definition = body.model_dump(exclude={"artifact_id", "data_source_id",
                                          "display_name"})
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        _artifact_or_forbidden(connection, body.artifact_id)
        _source_or_forbidden(connection, body.data_source_id)
        profile_run = datasets.latest_run(connection, body.artifact_id, "profile")
        profile = (profile_run or {}).get("result") or {}
        try:
            mapping = datasets.mapping_from_definition(definition)
        except datasets.PreparationError as error:
            raise ProblemError(problem(error.code, "Invalid mapping", 422,
                                       error.detail)) from None
        try:
            created = datasets.create_mapping(
                connection, company_id=context.company_id,
                data_source_id=body.data_source_id, artifact_id=body.artifact_id,
                display_name=body.display_name, definition=definition,
                subject_id=principal.subject_id,
                source_schema=datasets.schema_digest(profile))
        except datasets.MappingNameConflict:
            raise ProblemError(
                problem("mapping-name-conflict", "Mapping name already in use", 409,
                        "this company already has a mapping with that display name")
            ) from None
        except datasets.MappingReferenceRefused:
            logger.warning("mapping refused for company %s", context.company_id)
            raise forbidden() from None
        blockers = datasets.blockers_for(mapping, profile, [])
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="dataset.map",
            resource_kind="mapping", resource_ref=created["mapping_version_id"],
            outcome="allowed", detail={"artifact": body.artifact_id,
                                       "blockers": len(blockers)})
    return {**created, "blockers": blockers}


@router.get("/companies/{company_id}/mappings", tags=["mapping"])
def list_mappings(request: Request, company_id: str, artifact_id: str | None = None,
                  principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return datasets.list_mappings(connection, artifact_id=artifact_id)


@router.get("/companies/{company_id}/mappings/{mapping_version_id}", tags=["mapping"])
def read_mapping(request: Request, company_id: str, mapping_version_id: str,
                 principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        version = datasets.load_mapping_version(connection, mapping_version_id)
        if version is None:
            raise forbidden()
        profile_run = datasets.latest_run(connection, version["artifact_id"], "profile")
        profile = (profile_run or {}).get("result") or {}
        decisions = datasets.list_decisions(connection, mapping_version_id)
        mapping = datasets.mapping_from_definition(version["definition"])
        blockers = datasets.blockers_for(mapping, profile, decisions)
        unaccounted = datasets.unaccounted_columns(
            version["definition"], mapping, profile)
    return {**version, "decisions": decisions, "blockers": blockers,
            "unaccounted_columns": unaccounted,
            "columns": list(profile.get("columns") or [])}


@router.post("/companies/{company_id}/mappings/{mapping_version_id}/decisions",
             tags=["mapping"], status_code=201)
def decide_ambiguity(request: Request, company_id: str, mapping_version_id: str,
                     body: DecisionRequest,
                     principal: Principal = Depends(principal_dependency)) -> dict:
    """Deja escrita la eleccion de una persona sobre una ambiguedad."""
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        if datasets.load_mapping_version(connection, mapping_version_id) is None:
            raise forbidden()
        try:
            decision = datasets.record_decision(
                connection, company_id=context.company_id,
                mapping_version_id=mapping_version_id,
                ambiguity_kind=body.ambiguity_kind, subject_ref=body.subject_ref,
                resolved_value=body.resolved_value, rationale=body.rationale,
                subject_id=principal.subject_id)
        except Exception:  # noqa: BLE001 - vocabulario acotado por CHECK
            raise ProblemError(problem(
                "invalid-decision", "Invalid decision", 422,
                "the ambiguity kind is not one this system knows how to resolve")
            ) from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="dataset.decide",
            resource_kind="mapping", resource_ref=mapping_version_id,
            outcome="allowed",
            detail={"kind": body.ambiguity_kind, "subject": body.subject_ref,
                    "resolved": body.resolved_value})
    return decision


@router.post("/companies/{company_id}/mappings/{mapping_version_id}/validate",
             tags=["mapping"])
def validate_mapping(request: Request, company_id: str, mapping_version_id: str,
                     principal: Principal = Depends(principal_dependency)) -> dict:
    """Pasa el mapeo de borrador a validado, si ya no queda nada sin decidir."""
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        version = datasets.load_mapping_version(connection, mapping_version_id)
        if version is None:
            raise forbidden()
        profile_run = datasets.latest_run(connection, version["artifact_id"], "profile")
        profile = (profile_run or {}).get("result") or {}
        decisions = datasets.list_decisions(connection, mapping_version_id)
        mapping = datasets.mapping_from_definition(version["definition"])
        blockers = datasets.blockers_for(mapping, profile, decisions)
        if blockers:
            raise ProblemError(problem(
                "unresolved-ambiguity", "The mapping is not valid yet", 422,
                "a person has to resolve every finding before this mapping can "
                "produce a dataset", blockers=blockers))
        datasets.validate_mapping_version(
            connection, mapping_version_id=mapping_version_id,
            subject_id=principal.subject_id)
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="dataset.validate",
            resource_kind="mapping", resource_ref=mapping_version_id,
            outcome="allowed", detail={"artifact": version["artifact_id"]})
        return datasets.load_mapping_version(connection, mapping_version_id) or {}


@router.post("/companies/{company_id}/datasets", tags=["datasets"], status_code=201)
def prepare_dataset(request: Request, company_id: str, body: DatasetRequest,
                    response: Response,
                    principal: Principal = Depends(principal_dependency)) -> dict:
    """Convierte las filas extraidas en movimientos canonicos, por lotes.

    Devuelve **201** cuando el conjunto entero cabe en el presupuesto de tiempo, y
    **202** cuando no: entonces queda en `staging` —invisible como publicado— y se
    continua con `/continue`. Una peticion que durara minutos retendria una
    conexion del pool y no le serviria a nadie.

    Sale en `validated`, nunca en `published`: publicarlo es de otra persona.
    """
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        _artifact_or_forbidden(connection, body.artifact_id)

    try:
        prepared = datasets.prepare_dataset(
            database, company_id=context.company_id, artifact_id=body.artifact_id,
            mapping_version_id=body.mapping_version_id,
            financial_account_id=body.financial_account_id,
            subject_id=principal.subject_id,
            release_key=request.app.state.settings.engine_release_key)
    except datasets.PreparationError as error:
        raise _preparation_problem(error) from None
    except psycopg.errors.ForeignKeyViolation:
        # Una cuenta o una fuente de otra empresa. Indistinguible de que no
        # exista, por la misma razon de siempre.
        raise forbidden() from None

    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="dataset.prepare",
            resource_kind="dataset", resource_ref=prepared.dataset_version_id,
            outcome="allowed",
            detail={"movements": prepared.movement_count,
                    "rejected": prepared.rejected_count,
                    "chunks": prepared.chunks, "complete": prepared.complete})
    response.status_code = 201 if prepared.complete else 202
    return prepared.as_dict()


@router.post("/companies/{company_id}/datasets/{dataset_version_id}/continue",
             tags=["datasets"])
def continue_dataset(request: Request, company_id: str, dataset_version_id: str,
                     response: Response,
                     principal: Principal = Depends(principal_dependency)) -> dict:
    """Sigue una preparacion que se quedo en `staging`.

    Reanudar es idempotente: los lotes que ya entraron no se repiten, porque su
    fila de control entro con ellos y lo que no figura es lo que no ocurrio.
    """
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    try:
        prepared = datasets.continue_dataset(
            database, company_id=context.company_id,
            dataset_version_id=dataset_version_id, subject_id=principal.subject_id,
            release_key=request.app.state.settings.engine_release_key)
    except datasets.PreparationError as error:
        if error.code == "dataset-unknown":
            raise forbidden() from None
        raise _preparation_problem(error) from None
    response.status_code = 200 if prepared.complete else 202
    return prepared.as_dict()


@router.get("/companies/{company_id}/datasets", tags=["datasets"])
def list_datasets(request: Request, company_id: str, artifact_id: str | None = None,
                  principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return datasets.list_datasets(connection, artifact_id=artifact_id)


@router.get("/companies/{company_id}/datasets/{dataset_version_id}",
            tags=["datasets"])
def read_dataset(request: Request, company_id: str, dataset_version_id: str,
                 principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        dataset = datasets.load_dataset(connection, dataset_version_id)
        if dataset is None:
            raise forbidden()
        # Quien puede publicar necesita saber si **el** puede. Permiso, estado,
        # SoD, release y overrides se resuelven aqui; el navegador no es una
        # segunda autoridad y el POST usa la misma funcion de dominio.
        if "dataset.publish" not in context.permissions:
            blockers = [{"code": "permission-denied",
                         "detail": "this role cannot publish datasets"}]
        else:
            blockers = [item.as_dict() for item in datasets.publication_blockers(
                connection, dataset=dataset, subject_id=principal.subject_id)]
        dataset["publish_blockers"] = blockers
        dataset["can_publish"] = not blockers
    return dataset


@router.get("/companies/{company_id}/datasets/{dataset_version_id}/export",
            tags=["datasets"])
def export_dataset(request: Request, company_id: str, dataset_version_id: str,
                   principal: Principal = Depends(principal_dependency)) -> Response:
    """Transmite el dataset canonico publicado; nunca la evidencia original."""
    context = company_context(request, principal, company_id)
    require(context, "dataset.export")
    if request.app.state.settings.real_data_enabled:
        raise ProblemError(problem(
            "dataset-export-disabled", "Dataset export unavailable", 503,
            "dataset export is enabled only for synthetic data"))

    database = request.app.state.database
    refusal: exports.ExportError | None = None
    descriptor: exports.ExportDescriptor | None = None
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            descriptor = exports.preflight_export(connection, dataset_version_id)
        except exports.ExportError as error:
            refusal = error
        else:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="dataset.export.request",
                resource_kind="dataset", resource_ref=dataset_version_id,
                outcome="allowed",
                detail={"format": "csv", "profile": exports.EXPORT_PROFILE,
                        "rows": descriptor.row_count,
                        "canonical_schema_version":
                            descriptor.canonical_schema_version,
                        "reproduction_key": descriptor.reproduction_key})

    if refusal is not None:
        if refusal.code == "dataset-unknown":
            raise forbidden() from None
        with database.session(company_id=context.company_id,
                              subject_id=principal.subject_id) as connection:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="dataset.export.request",
                resource_kind="dataset", resource_ref=dataset_version_id,
                outcome="denied", detail={"reason": refusal.code})
        raise ProblemError(problem(
            refusal.code, "The dataset cannot be exported", 409,
            refusal.detail))

    assert descriptor is not None
    return StreamingResponse(
        exports.stream_dataset_csv(
            database, company_id=context.company_id,
            subject_id=principal.subject_id, descriptor=descriptor),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="{descriptor.filename}"',
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Fincilia-Export-Profile": exports.EXPORT_PROFILE,
            "X-Fincilia-Export-Rows": str(descriptor.row_count),
            "X-Fincilia-Canonical-Schema":
                descriptor.canonical_schema_version,
        },
    )


@router.post("/companies/{company_id}/datasets/{dataset_version_id}/publish",
             tags=["datasets"])
def publish_dataset(request: Request, company_id: str, dataset_version_id: str,
                    principal: Principal = Depends(principal_dependency)) -> dict:
    """Sella un dataset validado. Exige `dataset.publish` y otro sujeto."""
    context = company_context(request, principal, company_id)
    require(context, "dataset.publish")
    database = request.app.state.database
    refusal: datasets.PublicationError | None = None
    published: dict | None = None
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            published = datasets.publish_dataset(
                connection, dataset_version_id=dataset_version_id,
                subject_id=principal.subject_id)
        except datasets.PublicationError as error:
            # El rastro de la negativa **no** puede ir en esta transaccion:
            # levantar desde aqui la deshace, y la fila de auditoria se iria con
            # ella. Una negativa sin rastro es peor que no comprobar nada, porque
            # parece que nadie lo intento.
            refusal = error
        else:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="dataset.publish",
                resource_kind="dataset", resource_ref=dataset_version_id,
                outcome="allowed", detail={"movements": published["movement_count"],
                                           "engine": published["engine_release"]})

    if refusal is not None:
        if refusal.code == "dataset-unknown":
            raise forbidden()
        with database.session(company_id=context.company_id,
                              subject_id=principal.subject_id) as connection:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="dataset.publish",
                resource_kind="dataset", resource_ref=dataset_version_id,
                outcome="denied", detail={"reason": refusal.code})
        status = 409 if refusal.code in (
            "segregation-of-duties", "engine-release-not-approved") else 422
        raise ProblemError(problem(refusal.code, "The dataset cannot be published",
                                   status, refusal.detail))
    return published


@router.post("/companies/{company_id}/datasets/{dataset_version_id}/reject",
             tags=["datasets"])
def reject_dataset(request: Request, company_id: str, dataset_version_id: str,
                   body: RejectionRequest,
                   principal: Principal = Depends(principal_dependency)) -> dict:
    """Rechazar tambien es una decision del revisor, y tambien se audita."""
    context = company_context(request, principal, company_id)
    require(context, "dataset.publish")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            rejected = datasets.reject_dataset(
                connection, dataset_version_id=dataset_version_id,
                subject_id=principal.subject_id, reason=body.reason)
        except datasets.PublicationError as error:
            if error.code == "dataset-unknown":
                raise forbidden() from None
            raise ProblemError(problem(error.code, "The dataset cannot be rejected",
                                       422, error.detail)) from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="dataset.reject",
            resource_kind="dataset", resource_ref=dataset_version_id,
            outcome="denied", detail={"reason": body.reason[:120]})
    return rejected


@router.get("/companies/{company_id}/datasets/{dataset_version_id}/overrides",
            tags=["datasets"])
def list_overrides(request: Request, company_id: str, dataset_version_id: str,
                   principal: Principal = Depends(principal_dependency)) -> list[dict]:
    """Los overrides vigentes de un dataset, con quien los escribio y quien no."""
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        if datasets.load_dataset(connection, dataset_version_id) is None:
            raise forbidden()
        return datasets.list_overrides(connection,
                                       dataset_version_id=dataset_version_id)


@router.post("/companies/{company_id}/datasets/{dataset_version_id}/overrides",
             tags=["datasets"], status_code=201)
def create_override(request: Request, company_id: str, dataset_version_id: str,
                    body: OverrideRequest,
                    principal: Principal = Depends(principal_dependency)) -> dict:
    """Deja constancia de que una fila no se leyo como dice el plan.

    Exige `dataset.map`, el permiso de quien prepara: escribir el override es
    parte de preparar el dataset. Aprobarlo no, y por eso es otra ruta y otro
    permiso.
    """
    context = company_context(request, principal, company_id)
    require(context, "dataset.map")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            created = datasets.record_override(
                connection, company_id=context.company_id,
                dataset_version_id=dataset_version_id,
                source_record_id=body.source_record_id,
                field_name=body.field_name, override_kind=body.override_kind,
                base_step_ordinal=body.base_step_ordinal,
                original_value_digest=body.original_value_digest,
                resulting_value_digest=body.resulting_value_digest,
                reason_code=body.reason_code, subject_id=principal.subject_id)
        except datasets.OverrideError as error:
            if error.code == "override-target-unknown":
                raise forbidden() from None
            raise ProblemError(problem(
                error.code, "The override cannot be recorded",
                409 if error.code == "dataset-already-published" else 422,
                error.detail)) from None
        # Se audita el motivo, nunca el valor: el override existe para explicar
        # una decision, y registrar el importe aqui devolveria por la puerta de
        # atras lo que la tabla no guarda.
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="lineage.override",
            resource_kind="dataset", resource_ref=dataset_version_id,
            outcome="allowed",
            detail={"field": body.field_name, "kind": body.override_kind,
                    "reason_code": body.reason_code,
                    "needs_approval": created["needs_approval"]})
    return created


@router.post("/companies/{company_id}/overrides/{override_id}/approve",
             tags=["datasets"])
def approve_override(request: Request, company_id: str, override_id: str,
                     principal: Principal = Depends(principal_dependency)) -> dict:
    """Otro sujeto responde por el override. Exige `dataset.publish`.

    Quien aprueba una excepcion sobre un importe es quien podria publicarla, no
    quien la escribio.
    """
    context = company_context(request, principal, company_id)
    require(context, "dataset.publish")
    database = request.app.state.database
    refusal: datasets.OverrideError | None = None
    approved: dict | None = None
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            approved = datasets.approve_override(
                connection, override_id=override_id,
                subject_id=principal.subject_id)
        except datasets.OverrideError as error:
            refusal = error
        if refusal is None and approved is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="lineage.override.approve",
                resource_kind="dataset",
                resource_ref=approved["dataset_version_id"],
                outcome="allowed", detail={"override_id": override_id,
                                           "field": approved["field_name"]})
        elif refusal is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="lineage.override.approve",
                resource_kind="dataset", resource_ref=override_id,
                outcome="denied", detail={"reason": refusal.code})
    if refusal is not None:
        if refusal.code == "override-unknown":
            raise forbidden()
        raise ProblemError(problem(
            refusal.code, "The override cannot be approved",
            409 if refusal.code == "segregation-of-duties" else 422,
            refusal.detail))
    return approved


@router.get("/companies/{company_id}/datasets/{dataset_version_id}/movements",
            tags=["movements"])
def list_movements(request: Request, company_id: str, dataset_version_id: str,
                   offset: int = 0, limit: int = 50,
                   principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        if datasets.load_dataset(connection, dataset_version_id) is None:
            raise forbidden()
        return datasets.list_movements(connection,
                                       dataset_version_id=dataset_version_id,
                                       offset=offset, limit=limit)


@router.get("/companies/{company_id}/movements/{movement_id}", tags=["movements"])
def read_movement(request: Request, company_id: str, movement_id: str,
                  principal: Principal = Depends(principal_dependency)) -> dict:
    """Un movimiento con su camino hasta la celda que lo produjo."""
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        movement = datasets.load_movement(connection, movement_id)
        if movement is None:
            raise forbidden()
    return movement


@router.get("/companies/{company_id}/reconciliation/candidates",
            tags=["reconciliation"])
def reconciliation_candidates(
        request: Request, company_id: str, left_dataset_id: str,
        right_dataset_id: str,
        max_days: int = reconciliation.DEFAULT_DATE_WINDOW_DAYS,
        offset: int = 0, limit: int = reconciliation.DEFAULT_CANDIDATE_LIMIT,
        principal: Principal = Depends(principal_dependency)) -> dict:
    """Explora hipotesis exactas; nunca confirma ni persiste un match."""
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    # El gate de Settings hace hoy imposible encender datos reales. Esta guarda
    # explicita evita que una futura ampliacion habilite esta superficie por
    # accidente sin revisar primero privacidad y reglas contables.
    if request.app.state.settings.real_data_enabled:
        raise ProblemError(problem(
            "candidate-explorer-disabled", "Candidate explorer unavailable", 503,
            "candidate exploration is enabled only for synthetic data"))

    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            return reconciliation.explore_candidates(
                connection, left_dataset_id=left_dataset_id,
                right_dataset_id=right_dataset_id, max_days=max_days,
                offset=offset, limit=limit)
        except reconciliation.CandidateQueryError as error:
            if error.code == "candidate-scope-unavailable":
                raise forbidden() from None
            raise ProblemError(problem(
                error.code, "Candidate request invalid", 422, error.detail)) from None


def _synthetic_reconciliation_only(request: Request) -> None:
    if request.app.state.settings.real_data_enabled:
        raise ProblemError(problem(
            "reconciliation-review-disabled", "Reconciliation review unavailable",
            503, "reconciliation review is enabled only for synthetic data"))


def _review_problem(error: Exception) -> ProblemError:
    code = getattr(error, "code", "review-request-invalid")
    detail = getattr(error, "detail", "the review command is invalid")
    if code == "candidate-scope-unavailable":
        return forbidden()
    status = 409 if code in {
        "idempotency-conflict", "candidate-already-decided",
        "segregation-of-duties",
    } else 422
    return ProblemError(problem(code, "Reconciliation review rejected", status, detail))


@router.get("/companies/{company_id}/reconciliation/reviews",
            tags=["reconciliation"])
def reconciliation_reviews(
        request: Request, company_id: str, left_dataset_id: str,
        right_dataset_id: str, limit: int = 200,
        principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    _synthetic_reconciliation_only(request)
    with request.app.state.database.session(
            company_id=context.company_id,
            subject_id=principal.subject_id) as connection:
        try:
            return reconciliation.list_reviews(
                connection, left_dataset_id=left_dataset_id,
                right_dataset_id=right_dataset_id, limit=limit)
        except reconciliation.ReviewCommandError as error:
            raise _review_problem(error) from None


@router.get("/companies/{company_id}/reconciliation/review-queue",
            tags=["reconciliation"])
def reconciliation_review_queue(
        request: Request, company_id: str, status: str = "open",
        offset: int = 0, limit: int = 50,
        principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    _synthetic_reconciliation_only(request)
    with request.app.state.database.session(
            company_id=context.company_id,
            subject_id=principal.subject_id) as connection:
        try:
            return reconciliation.list_review_queue(
                connection, status=status, offset=offset, limit=limit)
        except reconciliation.ReviewCommandError as error:
            raise _review_problem(error) from None


@router.post("/companies/{company_id}/reconciliation/reviews",
             tags=["reconciliation"])
def propose_reconciliation_review(
        request: Request, company_id: str, body: MatchProposalRequest,
        principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    require(context, "match.propose")
    _synthetic_reconciliation_only(request)
    key = request.headers.get("idempotency-key", "")
    refusal: Exception | None = None
    result: dict | None = None
    with request.app.state.database.session(
            company_id=context.company_id,
            subject_id=principal.subject_id) as connection:
        try:
            result = reconciliation.propose_review(
                connection, company_id=context.company_id,
                actor_id=principal.subject_id, idempotency_key=key,
                left_dataset_id=body.left_dataset_id,
                right_dataset_id=body.right_dataset_id,
                left_movement_id=body.left_movement_id,
                right_movement_id=body.right_movement_id,
                max_days=body.max_days)
        except (reconciliation.ReviewCommandError,
                reconciliation.CandidateQueryError) as error:
            refusal = error
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action="match.propose",
                resource_kind="match_candidate", resource_ref="unmaterialized",
                outcome="denied", detail={"reason": error.code})
    if refusal is not None:
        raise _review_problem(refusal)
    if result is None:
        raise RuntimeError("review proposal completed without a result")
    return result


@router.post("/companies/{company_id}/reconciliation/reviews/{candidate_id}/decision",
             tags=["reconciliation"])
def decide_reconciliation_review(
        request: Request, company_id: str, candidate_id: str,
        body: MatchDecisionRequest,
        principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    permission = "match.confirm" if body.decision == "confirmed" else "match.reject"
    require(context, permission)
    _synthetic_reconciliation_only(request)
    key = request.headers.get("idempotency-key", "")
    refusal: reconciliation.ReviewCommandError | None = None
    result: dict | None = None
    with request.app.state.database.session(
            company_id=context.company_id,
            subject_id=principal.subject_id) as connection:
        try:
            result = reconciliation.decide_review(
                connection, company_id=context.company_id,
                actor_id=principal.subject_id, idempotency_key=key,
                candidate_id=candidate_id, decision=body.decision,
                reason_code=body.reason_code)
        except reconciliation.ReviewCommandError as error:
            refusal = error
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=context.company_id, action=f"match.{permission.rsplit('.', 1)[-1]}",
                resource_kind="match_candidate", resource_ref=candidate_id[:80],
                outcome="denied", detail={"reason": error.code})
    if refusal is not None:
        raise _review_problem(refusal)
    if result is None:
        raise RuntimeError("review decision completed without a result")
    return result


# --------------------------------------------------------------------------- #
# Alta de cuentas, fuentes, vinculos y ciclos (FNC-P3.5)
# --------------------------------------------------------------------------- #

class AccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_family: str
    display_name: str = Field(min_length=1, max_length=160)
    # El identificador entra por aqui y **no** sale por ningun sitio: se
    # tokeniza al recibirlo y lo que se guarda es el token.
    identifier: str = Field(min_length=4, max_length=64)
    currency_code: str = Field(min_length=3, max_length=3)
    timezone: str = "America/Bogota"


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    timezone: str | None = None
    status: str | None = None
    closed_reason: str | None = Field(default=None, max_length=200)


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_family: str
    display_name: str = Field(min_length=1, max_length=160)
    purpose_code: str = Field(default="operational", min_length=3, max_length=64)
    timezone: str = "America/Bogota"


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    purpose_code: str | None = Field(default=None, min_length=3, max_length=64)
    timezone: str | None = None
    status: str | None = None
    closed_reason: str | None = Field(default=None, max_length=200)


class LinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    financial_account_id: str
    relation_role: str = "primary"
    valid_from: dt.date | None = None


class LinkUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class CycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    periodicity: str = "monthly"
    custom_days: int | None = Field(default=None, ge=1, le=366)
    due_day_offset: int = Field(default=5, ge=0, le=120)
    grace_days: int = Field(default=3, ge=0, le=120)
    responsible_subject_id: str
    timezone: str = "America/Bogota"
    anchor_date: dt.date


class ExpectationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    until: dt.date


def _onboarding_problem(error: onboarding.OnboardingError) -> ProblemError:
    # `link-refused` no distingue «no existe» de «no puedes», por la misma razon
    # que el resto de la API: un codigo que las separara seria un buscador de
    # cuentas ajenas.
    # Un conflicto de estado es 409; una peticion mal formada, 422. Que ya
    # exista una cuenta principal no es un error de quien pide: es que el
    # mundo ya esta de otra manera.
    status = 409 if error.code in (
        "account-already-exists", "source-already-exists",
        "primary-already-set", "link-already-exists") else 422
    return ProblemError(problem(error.code, "The request cannot be applied", status,
                                error.detail))


@router.post("/companies/{company_id}/accounts", tags=["onboarding"], status_code=201)
def create_account(request: Request, company_id: str, body: AccountRequest,
                   principal: Principal = Depends(principal_dependency)) -> dict:
    """Da de alta una cuenta financiera.

    El identificador que llega en el cuerpo se convierte en token con una clave
    dedicada y **no se persiste, ni se registra, ni aparece en un error**. Lo que
    queda es el token, los cuatro ultimos digitos y la version de clave.
    """
    context = company_context(request, principal, company_id)
    require(context, "financial_account.manage")
    settings = request.app.state.settings
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            account = onboarding.create_account(
                connection, company_id=context.company_id,
                account_family=body.account_family,
                display_name=body.display_name, identifier=body.identifier,
                currency_code=body.currency_code, timezone=body.timezone,
                subject_id=principal.subject_id,
                tokenization_key=settings.identifier_tokenization_key,
                key_version=settings.identifier_key_version)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
        # El rastro dice que se creo una cuenta y cual es su cola visible. Nunca
        # el identificador: un evento de auditoria que lo llevara desharia la
        # tokenizacion entera.
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="account.create",
            resource_kind="financial_account",
            resource_ref=account["account_id"], outcome="allowed",
            detail={"family": account["account_family"],
                    "currency": account["currency_code"],
                    "last4": account.get("identifier_last4")})
    return account


@router.get("/companies/{company_id}/accounts", tags=["onboarding"])
def list_accounts(request: Request, company_id: str, include_inactive: bool = True,
                  principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return onboarding.list_accounts(connection, include_inactive=include_inactive)


@router.get("/companies/{company_id}/accounts/{account_id}", tags=["onboarding"])
def read_account(request: Request, company_id: str, account_id: str,
                 principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        account = onboarding.load_account(connection, account_id)
        if account is None:
            raise forbidden()
        account["usage"] = onboarding.account_usage(connection, account_id)
    return account


@router.patch("/companies/{company_id}/accounts/{account_id}", tags=["onboarding"])
def update_account(request: Request, company_id: str, account_id: str,
                   body: AccountUpdate,
                   principal: Principal = Depends(principal_dependency)) -> dict:
    """Cambia nombre, zona horaria o estado. **Nunca borra.**

    Una cuenta con movimientos publicados detras se cierra; borrarla dejaria
    hechos economicos apuntando a algo que nadie puede explicar.
    """
    context = company_context(request, principal, company_id)
    require(context, "financial_account.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        if onboarding.load_account(connection, account_id) is None:
            raise forbidden()
        try:
            account = onboarding.update_account(
                connection, account_id=account_id, display_name=body.display_name,
                timezone=body.timezone, status=body.status,
                closed_reason=body.closed_reason)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="account.update",
            resource_kind="financial_account", resource_ref=account_id,
            outcome="allowed",
            detail={"status": account.get("status"),
                    "reason": account.get("closed_reason")})
    return account


@router.post("/companies/{company_id}/sources", tags=["onboarding"], status_code=201)
def create_source(request: Request, company_id: str, body: SourceRequest,
                  principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            source = onboarding.create_source(
                connection, company_id=context.company_id,
                source_family=body.source_family, display_name=body.display_name,
                purpose_code=body.purpose_code, timezone=body.timezone)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="source.create",
            resource_kind="data_source", resource_ref=source["data_source_id"],
            outcome="allowed", detail={"family": source["source_family"]})
    return source


@router.get("/companies/{company_id}/sources", tags=["onboarding"])
def list_sources(request: Request, company_id: str, include_inactive: bool = True,
                 principal: Principal = Depends(principal_dependency)) -> list[dict]:
    """De donde viene la evidencia de esta empresa."""
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return onboarding.list_sources(connection, include_inactive=include_inactive)


@router.get("/companies/{company_id}/sources/{data_source_id}", tags=["onboarding"])
def read_source(request: Request, company_id: str, data_source_id: str,
                principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        source = onboarding.load_source(connection, data_source_id)
        if source is None:
            raise forbidden()
        source["links"] = onboarding.list_links(connection,
                                                data_source_id=data_source_id)
        source["cycle"] = onboarding.load_cycle(connection, data_source_id)
    return source


@router.patch("/companies/{company_id}/sources/{data_source_id}", tags=["onboarding"])
def update_source(request: Request, company_id: str, data_source_id: str,
                  body: SourceUpdate,
                  principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        if onboarding.load_source(connection, data_source_id) is None:
            raise forbidden()
        try:
            source = onboarding.update_source(
                connection, data_source_id=data_source_id,
                display_name=body.display_name, purpose_code=body.purpose_code,
                timezone=body.timezone, status=body.status,
                closed_reason=body.closed_reason)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="source.update",
            resource_kind="data_source", resource_ref=data_source_id,
            outcome="allowed", detail={"status": source.get("status")})
    return source


@router.post("/companies/{company_id}/sources/{data_source_id}/accounts",
             tags=["onboarding"], status_code=201)
def link_account(request: Request, company_id: str, data_source_id: str,
                 body: LinkRequest,
                 principal: Principal = Depends(principal_dependency)) -> dict:
    """Vincula una fuente con una cuenta y declara que papel juega."""
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            link = onboarding.link_account(
                connection, company_id=context.company_id,
                data_source_id=data_source_id,
                financial_account_id=body.financial_account_id,
                relation_role=body.relation_role, subject_id=principal.subject_id,
                valid_from=body.valid_from)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
        except psycopg.errors.ForeignKeyViolation:
            raise forbidden() from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="source.link",
            resource_kind="data_source", resource_ref=data_source_id,
            outcome="allowed", detail={"role": link["relation_role"],
                                       "account": link["financial_account_id"]})
    return link


@router.get("/companies/{company_id}/links", tags=["onboarding"])
def list_links(request: Request, company_id: str, data_source_id: str | None = None,
               principal: Principal = Depends(principal_dependency)) -> list[dict]:
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return onboarding.list_links(connection, data_source_id=data_source_id)


@router.patch("/companies/{company_id}/links/{link_id}", tags=["onboarding"])
def retire_link(request: Request, company_id: str, link_id: str, body: LinkUpdate,
                principal: Principal = Depends(principal_dependency)) -> dict:
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            link = onboarding.retire_link(connection, link_id=link_id,
                                          status=body.status)
        except onboarding.OnboardingError as error:
            if error.code == "link-unknown":
                raise forbidden() from None
            raise _onboarding_problem(error) from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="source.unlink",
            resource_kind="data_source", resource_ref=link["data_source_id"],
            outcome="allowed", detail={"status": link["status"]})
    return link


@router.put("/companies/{company_id}/sources/{data_source_id}/cycle",
            tags=["onboarding"])
def set_cycle(request: Request, company_id: str, data_source_id: str,
              body: CycleRequest,
              principal: Principal = Depends(principal_dependency)) -> dict:
    """Declara cada cuanto se espera un documento de esta fuente."""
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            cycle = onboarding.set_cycle(
                connection, company_id=context.company_id,
                data_source_id=data_source_id, periodicity=body.periodicity,
                custom_days=body.custom_days, due_day_offset=body.due_day_offset,
                grace_days=body.grace_days,
                responsible_subject_id=body.responsible_subject_id,
                timezone=body.timezone, anchor=body.anchor_date,
                subject_id=principal.subject_id)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
        except psycopg.errors.ForeignKeyViolation:
            raise forbidden() from None
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="source.cycle",
            resource_kind="data_source", resource_ref=data_source_id,
            # Quien queda como responsable es el hecho que importa de esta
            # llamada, y se registra por su identificador opaco: el nombre no
            # anade nada que el `subject_id` no resuelva, y si anade una copia
            # de un dato personal donde no toca.
            outcome="allowed", detail={"periodicity": cycle["periodicity"],
                                       "due_day_offset": cycle["due_day_offset"],
                                       "responsible": body.responsible_subject_id})
    return cycle


@router.post("/companies/{company_id}/sources/{data_source_id}/expectations",
             tags=["onboarding"], status_code=201)
def generate_expectations(request: Request, company_id: str, data_source_id: str,
                          body: ExpectationRequest,
                          principal: Principal = Depends(principal_dependency)) -> dict:
    """Materializa los periodos del ciclo hasta una fecha. Idempotente."""
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        try:
            report = onboarding.generate_expectations(
                connection, company_id=context.company_id,
                data_source_id=data_source_id, until=body.until)
        except onboarding.OnboardingError as error:
            raise _onboarding_problem(error) from None
    return {"data_source_id": data_source_id, **report}


@router.get("/companies/{company_id}/expectations", tags=["onboarding"])
def list_expectations(request: Request, company_id: str,
                      data_source_id: str | None = None, limit: int = 100,
                      principal: Principal = Depends(principal_dependency),
                      ) -> list[dict]:
    """Que se espera, cuando vence y que lleva atraso.

    El atraso se calcula al leer contra la fecha de hoy. Guardarlo obligaria a un
    proceso nocturno que marcara atrasos, y el dia que no corriera nada estaria
    atrasado.
    """
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return onboarding.list_expectations(
            connection, today=dt.date.today(), data_source_id=data_source_id,
            limit=limit)


@router.get("/companies/{company_id}/assignees", tags=["onboarding"])
def list_assignees(request: Request, company_id: str,
                   principal: Principal = Depends(principal_dependency)) -> list[dict]:
    """Quien puede responder de un ciclo en esta empresa.

    Pide `data_source.manage` y no `company.read`: es la lectura de quien va a
    asignar una tarea, no un directorio de personas. Devuelve el identificador
    opaco, el nombre visible y los roles **en esta empresa**; ni correo, ni
    vinculo externo, ni en que otras firmas milita alguien.

    Se resuelve contra la base en cada peticion. Cachearlo en Valkey haria que
    revocar a alguien tardara en notarse lo que tarde una entrada en caducar, y
    durante ese rato la cache seria la autoridad sobre quien puede.
    """
    context = company_context(request, principal, company_id)
    require(context, "data_source.manage")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        people = onboarding.eligible_assignees(connection)
        # Consultar quien puede recibir una tarea es una lectura sobre personas,
        # y deja rastro. Cuantas, no quienes.
        repository.record_audit(
            connection, subject_id=principal.subject_id,
            company_id=context.company_id, action="assignee.list",
            resource_kind="company", resource_ref=context.company_id,
            outcome="allowed", detail={"candidates": len(people)})
    return people
