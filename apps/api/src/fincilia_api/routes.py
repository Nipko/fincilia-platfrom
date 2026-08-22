"""Endpoints de identidad, empresas y auditoria.

Un principio recorre el fichero: **el cliente propone, el servidor decide**. El
`company_id` de la ruta se compara contra lo que la base autoriza, y toda lectura
ocurre dentro de una transaccion cuyo alcance ya esta fijado. Filtrar en Python
lo que deberia filtrar la politica es como se construyen las fugas que ninguna
prueba de caso feliz encuentra.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from fincilia_contracts.tenancy import TenantContext
from fincilia_platform.identity import AuthenticationError
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


def principal_dependency(request: Request) -> Principal:
    return current_principal(request)


@router.post("/auth/session", response_model=SessionResponse, tags=["identity"])
async def open_session(request: Request, body: SessionRequest) -> SessionResponse:
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
async def me(request: Request,
             principal: Principal = Depends(principal_dependency)) -> dict:
    companies = _my_companies(request, principal)
    return {
        "subject_id": principal.subject_id,
        "display_name": principal.display_name,
        "session_expires_at": principal.claims.expires_at,
        "companies": [item.model_dump() for item in companies],
    }


@router.get("/companies", response_model=list[CompanySummary], tags=["companies"])
async def list_companies(request: Request,
                         principal: Principal = Depends(principal_dependency),
                         ) -> list[CompanySummary]:
    return _my_companies(request, principal)


@router.get("/companies/{company_id}", response_model=CompanyDetail,
            tags=["companies"])
async def read_company(request: Request, company_id: str,
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
async def read_audit(request: Request, company_id: str, limit: int = 50,
                     principal: Principal = Depends(principal_dependency),
                     ) -> list[AuditEvent]:
    context: TenantContext = company_context(request, principal, company_id)
    require(context, "audit.read")
    database = request.app.state.database
    with database.session(company_id=context.company_id,
                          subject_id=principal.subject_id) as connection:
        events = repository.list_audit(connection, limit=limit)
    return [AuditEvent(**event) for event in events]
