"""Resolucion de identidad y alcance para cada peticion.

Orden deliberado, y cada paso puede denegar:

1. el token se verifica antes de leerlo;
2. el sujeto se relee de la base, porque suspender una cuenta no puede esperar a
   que caduque un token emitido antes;
3. la empresa que pide el cliente se compara contra lo que la base autoriza; no
   la define;
4. si los permisos de esa empresa cambiaron despues de emitir el token, se exige
   volver a autenticarse: un token anterior a una revocacion no puede seguir
   sirviendo.

Ningun mensaje de error dice si el recurso existe. Quien recibe un 403 no debe
aprender de el que la empresa esta ahi.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from fastapi import HTTPException, Request

from fincilia_contracts.errors import ProblemDetail, problem
from fincilia_contracts.tenancy import AuthorizationError, TenantContext
from fincilia_platform.tokens import Claims, TokenError, verify

from . import repository

BEARER = "Bearer "


class ProblemError(HTTPException):
    """Un fallo que ya sabe como se serializa en RFC 7807."""

    def __init__(self, detail: ProblemDetail) -> None:
        super().__init__(status_code=detail.status, detail=detail.detail)
        self.problem = detail


def unauthorized(reason: str) -> ProblemError:
    return ProblemError(problem("unauthenticated", "Authentication required", 401,
                                reason))


def forbidden() -> ProblemError:
    # Un unico texto para toda denegacion: distinguir «no existe» de «no puedes»
    # convierte el codigo de error en un buscador de empresas.
    return ProblemError(problem("forbidden", "Not authorised", 403,
                                "the requested resource is not available in this context"))


@dataclass(frozen=True)
class Principal:
    subject_id: str
    display_name: str
    claims: Claims


def bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if not header.startswith(BEARER):
        raise unauthorized("a bearer token is required")
    token = header[len(BEARER):].strip()
    if not token:
        raise unauthorized("a bearer token is required")
    return token


def current_principal(request: Request) -> Principal:
    settings = request.app.state.settings
    database = request.app.state.database
    try:
        claims = verify(bearer_token(request), key=settings.auth_signing_key,
                        issuer=settings.auth_issuer, audience=settings.auth_audience,
                        now=int(time.time()))
    except TokenError:
        raise unauthorized("the session is not valid") from None

    with database.session(subject_id=claims.subject_id) as connection:
        subject = repository.load_subject(connection, claims.subject_id)
    if subject is None or not subject.active:
        # Reunir el sujeto en cada peticion es el precio de poder suspender una
        # cuenta y que surta efecto ya, no cuando caduque el token.
        raise unauthorized("the session is not valid")
    return Principal(subject.subject_id, subject.display_name, claims)


def company_context(request: Request, principal: Principal,
                    claimed_company_id: str) -> TenantContext:
    """Contexto verificado para una empresa, o denegacion auditada."""
    try:
        # Un identificador con otra forma no llega a la base: `uuid = texto` es un
        # error de tipo, y un 500 le diria al cliente que su cadena viajo mas
        # lejos de lo que deberia.
        uuid.UUID(claimed_company_id)
    except (ValueError, AttributeError, TypeError):
        raise forbidden() from None
    database = request.app.state.database
    denial: str | None = None
    with database.session(company_id=claimed_company_id,
                          subject_id=principal.subject_id) as connection:
        granted = repository.authorize(connection, principal.subject_id,
                                       claimed_company_id)
        if granted is None:
            denial = "no_active_authorization"
        elif granted.version_updated_at > principal.claims.issued_at:
            denial = "stale_authorization"
        if denial is not None:
            repository.record_audit(
                connection, subject_id=principal.subject_id,
                company_id=claimed_company_id, action="company.access",
                resource_kind="company", resource_ref=claimed_company_id,
                outcome="denied",
                detail={"reason": denial} if granted is None
                else {"reason": denial, "version": granted.version})
    # Fuera del `with`, y por tanto despues del commit. Lanzar dentro deshacia la
    # transaccion que acababa de registrar la denegacion: el rastro desaparecia
    # justo en el caso en que mas falta hace.
    if denial == "stale_authorization":
        raise unauthorized("authorisation changed; sign in again")
    if denial is not None or granted is None:
        raise forbidden()

    try:
        context = TenantContext(
            subject_id=principal.subject_id, firm_id=granted.firm_id,
            company_id=granted.company_id, roles=granted.roles,
            authorization_version=granted.version,
            engagement_id=granted.engagement_id)
    except AuthorizationError:
        raise forbidden() from None
    # El identificador que envio el cliente se compara contra el autorizado. Son
    # el mismo por construccion; comprobarlo aqui hace que deje de serlo si
    # alguien cambia el orden de los pasos de arriba.
    context.require_company(claimed_company_id)
    return context


def require(context: TenantContext, permission: str) -> None:
    try:
        context.require(permission)
    except AuthorizationError:
        raise forbidden() from None
