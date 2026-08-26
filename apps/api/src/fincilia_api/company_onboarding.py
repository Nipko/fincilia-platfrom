"""Alta atomica de company, engagement y configuracion operativa inicial.

La firma no posee la empresa: la transaccion crea una ``company`` estable y un
``engagement`` revocable. El primer owner lo concede la autoridad tecnica de
aprovisionamiento, que no tiene credencial ni grant y no puede operar.

Los dos identificadores sensibles entran una vez y se convierten en HMAC antes
de tocar SQL. Ni la respuesta idempotente ni la auditoria conservan sus valores.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from fincilia_contracts.tenancy import (
    AuthorizationError,
    derive_permissions,
    derive_firm_permissions,
    require_firm_permission,
)
from fincilia_contracts.tokenization import TokenizationError, tokenize

from . import onboarding, repository

PROVISIONING_AUTHORITY_ID = "4d1d048f-07af-5ccd-bd76-abace2124b63"
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
SUPPORTED_COUNTRIES = frozenset({"AR", "CL", "CO", "MX", "PE"})


class CompanyOnboardingError(Exception):
    """La solicitud no se puede ejecutar; el mensaje nunca cita identificadores."""

    def __init__(self, code: str, detail: str, *, status: int = 422) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class InitialSetup:
    account_family: str
    account_name: str
    account_identifier: str
    currency_code: str
    source_family: str
    source_name: str
    purpose_code: str
    timezone: str
    anchor_date: date
    due_day_offset: int = 0
    grace_days: int = 3


def _normalised_name(value: str) -> str:
    name = value.strip()
    if not 2 <= len(name) <= 300:
        raise CompanyOnboardingError(
            "invalid-company-name", "the legal name is between 2 and 300 characters")
    return name


def _country(value: str) -> str:
    country = value.strip().upper()
    if country not in SUPPORTED_COUNTRIES:
        raise CompanyOnboardingError(
            "unsupported-country", "the selected country is not supported yet")
    return country


def _tokens(*, tax_identifier: str, country_code: str,
            setup: InitialSetup | None, firm_id: str,
            tokenization_key: str, key_version: int) -> tuple[str, str | None]:
    try:
        tax_token = tokenize(
            tax_identifier, key=tokenization_key, key_version=key_version,
            account_family="company_tax_id", company_id=country_code,
        ).token
        account_request_token = None
        if setup is not None:
            # Esta huella sirve solo para detectar que la misma clave de
            # idempotencia intento cambiar de cuenta. La persistida se vuelve a
            # producir luego, aislada por company_id.
            account_request_token = tokenize(
                setup.account_identifier, key=tokenization_key,
                key_version=key_version, account_family=setup.account_family,
                company_id=f"provisioning:{firm_id}",
            ).token
    except TokenizationError as error:
        raise CompanyOnboardingError("invalid-identifier", str(error)) from None
    return tax_token, account_request_token


def _request_digest(*, firm_id: str, legal_name: str, country_code: str,
                    tax_token: str, setup: InitialSetup | None,
                    account_request_token: str | None) -> str:
    material: dict[str, Any] = {
        "firm_id": firm_id,
        "legal_name": legal_name,
        "country_code": country_code,
        "tax_token": tax_token,
        "setup": None,
    }
    if setup is not None:
        material["setup"] = {
            "account_family": setup.account_family,
            "account_name": setup.account_name.strip(),
            "account_token": account_request_token,
            "currency_code": setup.currency_code.upper(),
            "source_family": setup.source_family,
            "source_name": setup.source_name.strip(),
            "purpose_code": setup.purpose_code.strip(),
            "timezone": setup.timezone,
            "anchor_date": setup.anchor_date.isoformat(),
            "due_day_offset": setup.due_day_offset,
            "grace_days": setup.grace_days,
        }
    serialised = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _assert_firm_manager(connection: psycopg.Connection, *, firm_id: str,
                         subject_id: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT m.firm_role FROM fincilia.membership m "
            "JOIN fincilia.firm f ON f.firm_id = m.firm_id "
            "WHERE m.firm_id = %s AND m.subject_id = %s "
            "  AND m.status = 'active' AND f.status = 'active'",
            (firm_id, subject_id),
        )
        row = cursor.fetchone()
    try:
        if row is None:
            raise AuthorizationError("firm membership unavailable")
        require_firm_permission(row[0], "company.provision")
    except AuthorizationError:
        # Firma inexistente y firma ajena son indistinguibles.
        raise CompanyOnboardingError(
            "firm-access-denied", "the firm is not available for provisioning",
            status=403,
        )


def list_manageable_firms(connection: psycopg.Connection, *,
                          subject_id: str) -> list[dict[str, str]]:
    """Firmas activas donde el sujeto puede aprovisionar una company."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT f.firm_id::text, f.legal_name, m.firm_role "
            "FROM fincilia.membership m "
            "JOIN fincilia.firm f ON f.firm_id = m.firm_id "
            "WHERE m.subject_id = %s AND m.status = 'active' "
            "  AND f.status = 'active' ORDER BY f.legal_name, f.firm_id",
            (subject_id,),
        )
        rows = cursor.fetchall()
    return [
        {"firm_id": row[0], "legal_name": row[1], "firm_role": row[2]}
        for row in rows
        if "company.provision" in derive_firm_permissions(row[2])
    ]


def _reserve(connection: psycopg.Connection, *, command_id: str,
             subject_id: str, firm_id: str, idempotency_key: str,
             request_digest: str) -> dict[str, Any] | None:
    """Reserva la clave antes de crear filas; el perdedor espera y reproduce."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO fincilia.company_provisioning_command "
            "(command_id, subject_id, firm_id, idempotency_key, request_digest) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (subject_id, idempotency_key) DO NOTHING",
            (command_id, subject_id, firm_id, idempotency_key, request_digest),
        )
        if cursor.rowcount:
            return None
        cursor.execute(
            "SELECT request_digest, state, result "
            "FROM fincilia.company_provisioning_command "
            "WHERE subject_id = %s AND idempotency_key = %s",
            (subject_id, idempotency_key),
        )
        row = cursor.fetchone()
    if row is None or row[0] != request_digest:
        raise CompanyOnboardingError(
            "idempotency-conflict",
            "the idempotency key already names a different request",
            status=409,
        )
    if row[1] != "completed" or row[2] is None:
        raise CompanyOnboardingError(
            "idempotency-incomplete", "the previous provisioning did not complete",
            status=409,
        )
    return dict(row[2])


def provision_company(connection: psycopg.Connection, *, company_id: str,
                      firm_id: str, subject_id: str, legal_name: str,
                      country_code: str, tax_identifier: str,
                      idempotency_key: str, tokenization_key: str,
                      key_version: int, setup: InitialSetup | None) -> dict[str, Any]:
    """Crea toda la vertical o ninguna fila; una repeticion devuelve el recibo."""
    if not IDEMPOTENCY_KEY.fullmatch(idempotency_key):
        raise CompanyOnboardingError(
            "invalid-idempotency-key", "the idempotency key has an invalid shape")
    name = _normalised_name(legal_name)
    country = _country(country_code)
    _assert_firm_manager(connection, firm_id=firm_id, subject_id=subject_id)
    tax_token, account_request_token = _tokens(
        tax_identifier=tax_identifier, country_code=country, setup=setup,
        firm_id=firm_id, tokenization_key=tokenization_key,
        key_version=key_version,
    )
    digest = _request_digest(
        firm_id=firm_id, legal_name=name, country_code=country,
        tax_token=tax_token, setup=setup,
        account_request_token=account_request_token,
    )
    command_id = str(uuid.uuid4())
    replay = _reserve(
        connection, command_id=command_id, subject_id=subject_id,
        firm_id=firm_id, idempotency_key=idempotency_key,
        request_digest=digest,
    )
    if replay is not None:
        return {**replay, "replayed": True}

    with connection.cursor() as cursor:
        try:
            with connection.transaction():
                cursor.execute(
                    "INSERT INTO fincilia.company "
                    "(company_id, legal_name, tax_id_token, tax_id_key_version, "
                    " country_code) VALUES (%s, %s, %s, %s, %s)",
                    (company_id, name, tax_token, key_version, country),
                )
        except psycopg.errors.UniqueViolation:
            # No se revela si existe, quien la administra ni bajo que nombre.
            raise CompanyOnboardingError(
                "company-already-registered",
                "a company with that protected tax identity is already registered",
                status=409,
            ) from None

        cursor.execute(
            "INSERT INTO fincilia.authorization_version (company_id, version) "
            "VALUES (%s, 1)", (company_id,))
        engagement_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO fincilia.engagement "
            "(engagement_id, firm_id, company_id, valid_from, "
            " is_primary_operator) VALUES (%s, %s, %s, CURRENT_DATE, true)",
            (engagement_id, firm_id, company_id),
        )
        cursor.execute(
            "INSERT INTO fincilia.company_grant "
            "(grant_id, company_id, subject_id, company_role, granted_by) "
            "VALUES (gen_random_uuid(), %s, %s, 'owner', %s)",
            (company_id, subject_id, PROVISIONING_AUTHORITY_ID),
        )

    account_id = source_id = link_id = cycle_id = None
    expectations_created = 0
    if setup is not None:
        try:
            account = onboarding.create_account(
                connection, company_id=company_id,
                account_family=setup.account_family,
                display_name=setup.account_name,
                identifier=setup.account_identifier,
                currency_code=setup.currency_code,
                timezone=setup.timezone,
                subject_id=subject_id,
                tokenization_key=tokenization_key,
                key_version=key_version,
            )
            source = onboarding.create_source(
                connection, company_id=company_id,
                source_family=setup.source_family,
                display_name=setup.source_name,
                purpose_code=setup.purpose_code,
                timezone=setup.timezone,
            )
            link = onboarding.link_account(
                connection, company_id=company_id,
                data_source_id=source["data_source_id"],
                financial_account_id=account["account_id"],
                relation_role="primary", subject_id=subject_id,
            )
            cycle = onboarding.set_cycle(
                connection, company_id=company_id,
                data_source_id=source["data_source_id"], periodicity="monthly",
                custom_days=None, due_day_offset=setup.due_day_offset,
                grace_days=setup.grace_days,
                responsible_subject_id=subject_id, timezone=setup.timezone,
                anchor=setup.anchor_date, subject_id=subject_id,
            )
            generated = onboarding.generate_expectations(
                connection, company_id=company_id,
                data_source_id=source["data_source_id"], until=setup.anchor_date,
            )
        except onboarding.OnboardingError as error:
            raise CompanyOnboardingError(error.code, error.detail) from None
        account_id = account["account_id"]
        source_id = source["data_source_id"]
        link_id = link["link_id"]
        cycle_id = cycle["cycle_id"]
        expectations_created = generated["created"]

    result = {
        "company_id": company_id,
        "legal_name": name,
        "country_code": country,
        "status": "active",
        "firm_id": firm_id,
        "engagement_id": engagement_id,
        "authorization_version": 1,
        "roles": ["owner"],
        "permissions": sorted(derive_permissions(("owner",))),
        "account_id": account_id,
        "source_id": source_id,
        "link_id": link_id,
        "cycle_id": cycle_id,
        "expectations_created": expectations_created,
        "replayed": False,
    }
    repository.record_audit(
        connection, subject_id=subject_id, company_id=company_id,
        action="company.provision", resource_kind="company",
        resource_ref=company_id, outcome="allowed",
        detail={
            "country_code": country,
            "initial_account": account_id is not None,
            "initial_source": source_id is not None,
            "initial_cycle": cycle_id is not None,
        },
    )
    stored = {key: value for key, value in result.items() if key != "replayed"}
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.company_provisioning_command "
            "SET state = 'completed', company_id = %s, result = %s, "
            "    completed_at = now() WHERE command_id = %s",
            (company_id, Jsonb(stored), command_id),
        )
    return result
