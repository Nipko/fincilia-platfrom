"""Endpoints de identidad, empresas y auditoria.

Un principio recorre el fichero: **el cliente propone, el servidor decide**. El
`company_id` de la ruta se compara contra lo que la base autoriza, y toda lectura
ocurre dentro de una transaccion cuyo alcance ya esta fijado. Filtrar en Python
lo que deberia filtrar la politica es como se construyen las fugas que ninguna
prueba de caso feliz encuentra.
"""

from __future__ import annotations

import hashlib
import logging
import time

import psycopg

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from fincilia_contracts.ingestion import MAX_UPLOAD_BYTES, RejectedUpload, admit
from fincilia_contracts.tenancy import TenantContext
from fincilia_platform.identity import AuthenticationError
from fincilia_platform.objects import ObjectStoreError, object_key
from fincilia_platform.tokens import issue

from . import datasets, repository
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


def _artifact_or_forbidden(connection, artifact_id: str):
    """El artefacto, o una denegacion indistinguible de «no existe».

    Un codigo que separa «no existe» de «no puedes» convierte la API en un
    buscador de documentos ajenos, y eso vale para toda esta seccion igual que
    para la de documentos.
    """
    artifact = repository.find_artifact_by_id(connection, artifact_id)
    if artifact is None:
        raise forbidden()
    return artifact


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
        except Exception:  # noqa: BLE001 - una referencia ajena no se distingue
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
        # Quien puede publicar necesita saber si **el** puede: la respuesta
        # incluye si este sujeto seria el autor, para que el boton no mienta.
        dataset["can_publish"] = (
            "dataset.publish" in context.permissions
            and dataset["state"] == "validated"
            and dataset["prepared_by"] != principal.subject_id)
    return dataset


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


@router.get("/companies/{company_id}/accounts", tags=["mapping"])
def list_accounts(request: Request, company_id: str,
                  principal: Principal = Depends(principal_dependency)) -> list[dict]:
    """Las cuentas de la empresa. Un movimiento siempre se registra contra una."""
    context = company_context(request, principal, company_id)
    require(context, "movement.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return datasets.list_accounts(connection)


@router.get("/companies/{company_id}/sources", tags=["mapping"])
def list_sources(request: Request, company_id: str,
                 principal: Principal = Depends(principal_dependency)) -> list[dict]:
    """De donde viene la evidencia de esta empresa."""
    context = company_context(request, principal, company_id)
    require(context, "document.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        return datasets.list_sources(connection)
