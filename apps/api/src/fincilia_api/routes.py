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

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from fincilia_contracts.ingestion import MAX_UPLOAD_BYTES, RejectedUpload, admit
from fincilia_contracts.tenancy import TenantContext
from fincilia_platform.identity import AuthenticationError
from fincilia_platform.objects import ObjectStoreError, object_key
from fincilia_platform.tokens import issue

from . import repository
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
