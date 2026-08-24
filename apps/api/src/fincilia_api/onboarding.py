"""Alta de cuentas, fuentes, vinculos y ciclos esperados.

Es lo que faltaba para que el producto sirviera sin sembrar la base a mano. Un
movimiento canonico exige una cuenta y un registro de origen exige una fuente;
sin forma de crearlas, la unica manera de publicar era editar la semilla.

Dos reglas gobiernan este modulo:

* **el identificador de una cuenta no se persiste en claro, ni se registra, ni
  aparece en un mensaje de error.** Entra, se convierte en token con una clave
  dedicada, y lo que queda es el token, los cuatro ultimos digitos y la version
  de clave. Un error que citara el numero convertiria la tokenizacion en teatro;
* **nada se borra.** Una cuenta con evidencia detras se cierra, no desaparece:
  borrarla dejaria movimientos publicados apuntando a algo que nadie puede
  explicar. `ON DELETE RESTRICT` lo impide en el motor, y aqui se dice antes con
  un mensaje que se entiende.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import psycopg

from fincilia_contracts.cycles import CycleError, periods_between, validate_cycle
from fincilia_contracts.money import SUPPORTED_CURRENCIES
from fincilia_contracts.tokenization import TokenizationError, tokenize

logger = logging.getLogger("fincilia.api.onboarding")

ACCOUNT_FAMILIES = ("bank_account", "payment_gateway", "merchant_acquirer",
                    "marketplace", "digital_wallet", "billing_erp",
                    "accounting_ledger")
SOURCE_FAMILIES = ACCOUNT_FAMILIES + ("tax_documents_received",
                                      "supporting_evidence", "reference_data")
RELATION_ROLES = ("primary", "settlement", "ledger", "supporting")
LIFECYCLE = ("active", "suspended", "closed")

# Zonas horarias que este producto admite hoy. La lista es corta a proposito: una
# zona mal escrita desplaza el cierre de un dia entero, y aceptar cualquier texto
# convierte ese error en algo que solo se descubre conciliando.
TIMEZONES = ("America/Bogota", "America/Lima", "America/Mexico_City",
             "America/Santiago", "America/Argentina/Buenos_Aires", "UTC")


class OnboardingError(Exception):
    """El alta no procede, y el motivo es de quien la pide."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _one(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cursor.description], row))


def _all(cursor) -> list[dict[str, Any]]:
    columns = [d[0] for d in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _stamp(row: dict[str, Any]) -> dict[str, Any]:
    return {key: (value.isoformat() if hasattr(value, "isoformat") else
                  str(value) if key.endswith("_id") and value is not None else value)
            for key, value in row.items()}


def _check_common(*, display_name: str, timezone: str) -> None:
    if not 1 <= len(display_name.strip()) <= 160:
        raise OnboardingError("invalid-name",
                              "the visible name is between 1 and 160 characters")
    if timezone not in TIMEZONES:
        raise OnboardingError(
            "invalid-timezone",
            f"{timezone!r} is not a timezone this product supports; a wrong one "
            "shifts the whole close by a day")


# --------------------------------------------------------------------------- #
# Cuentas
# --------------------------------------------------------------------------- #

def create_account(connection: psycopg.Connection, *, company_id: str,
                   account_family: str, display_name: str, identifier: str,
                   currency_code: str, timezone: str, subject_id: str,
                   tokenization_key: str, key_version: int) -> dict[str, Any]:
    """Da de alta una cuenta. El identificador entra y **no** se guarda.

    El duplicado se detecta comparando tokens, que es lo que permite decir «esta
    cuenta ya esta» sin haber guardado ningun numero para poder decirlo.
    """
    _check_common(display_name=display_name, timezone=timezone)
    if account_family not in ACCOUNT_FAMILIES:
        raise OnboardingError("invalid-family",
                              f"{account_family!r} is not an account family")
    if currency_code.upper() not in SUPPORTED_CURRENCIES:
        raise OnboardingError(
            "invalid-currency",
            f"{currency_code!r} is not a supported ISO currency; a number without "
            "a unit is not money")
    try:
        token = tokenize(identifier, key=tokenization_key, key_version=key_version,
                         account_family=account_family, company_id=company_id)
    except TokenizationError as error:
        # El mensaje viene del modulo de tokenizacion, que nunca cita el valor.
        raise OnboardingError("invalid-identifier", str(error)) from None

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT account_id, display_name FROM fincilia.financial_account "
            "WHERE company_id = %s AND account_family = %s AND identifier_token = %s",
            (company_id, account_family, token.token))
        existing = _one(cursor)
        if existing is not None:
            raise OnboardingError(
                "account-already-exists",
                f"this company already has that account, registered as "
                f"{existing['display_name']!r}")

        cursor.execute(
            "INSERT INTO fincilia.financial_account (account_id, company_id, "
            "account_family, display_name, identifier_token, identifier_last4, "
            "identifier_key_version, currency_code, timezone) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING account_id, account_family, display_name, identifier_last4, "
            "          identifier_key_version, currency_code, timezone, status, "
            "          created_at",
            (company_id, account_family, display_name.strip(), token.token,
             token.last4, token.key_version, currency_code.upper(), timezone))
        return _stamp(_one(cursor) or {})


def list_accounts(connection: psycopg.Connection, *,
                  include_inactive: bool = True) -> list[dict[str, Any]]:
    """Las cuentas de la empresa. Nunca el identificador, solo su cola visible."""
    statement = (
        "SELECT account_id, account_family, display_name, identifier_last4, "
        "       currency_code, timezone, status, closed_reason, created_at, "
        "       updated_at FROM fincilia.financial_account ")
    if not include_inactive:
        statement += "WHERE status = 'active' "
    statement += "ORDER BY display_name"
    with connection.cursor() as cursor:
        cursor.execute(statement)
        return [_stamp(row) for row in _all(cursor)]


def load_account(connection: psycopg.Connection,
                 account_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT account_id, account_family, display_name, identifier_last4, "
            "       identifier_key_version, currency_code, timezone, status, "
            "       closed_reason, created_at, updated_at "
            "FROM fincilia.financial_account WHERE account_id = %s", (account_id,))
        row = _one(cursor)
    return _stamp(row) if row else None


def update_account(connection: psycopg.Connection, *, account_id: str,
                   display_name: str | None = None, timezone: str | None = None,
                   status: str | None = None,
                   closed_reason: str | None = None) -> dict[str, Any]:
    """Cambia lo que se puede cambiar. La moneda y la familia no estan.

    Cambiar la moneda de una cuenta con movimientos publicados reinterpretaria
    importes que ya se contaron, y cambiar la familia cambiaria que significa su
    identificador. Las dos son cuentas distintas, no la misma editada.
    """
    current = load_account(connection, account_id)
    if current is None:
        raise OnboardingError("account-unknown", "no such account")
    if display_name is not None or timezone is not None:
        _check_common(display_name=display_name or current["display_name"],
                      timezone=timezone or current["timezone"])
    if status is not None and status not in LIFECYCLE:
        raise OnboardingError("invalid-status", f"{status!r} is not a lifecycle state")
    if status is not None and status != "active" and not (closed_reason or "").strip():
        raise OnboardingError(
            "reason-required",
            "suspending or closing an account is a decision, and a decision "
            "carries its reason")

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.financial_account SET "
            "  display_name = coalesce(%s, display_name), "
            "  timezone = coalesce(%s, timezone), "
            "  status = coalesce(%s, status), "
            "  closed_reason = CASE WHEN coalesce(%s, status) = 'active' "
            "                       THEN NULL ELSE %s END, "
            "  updated_at = now() "
            "WHERE account_id = %s "
            "RETURNING account_id, account_family, display_name, identifier_last4, "
            "          currency_code, timezone, status, closed_reason, updated_at",
            (display_name.strip() if display_name else None, timezone, status,
             status, (closed_reason or "").strip() or None, account_id))
        return _stamp(_one(cursor) or {})


def account_usage(connection: psycopg.Connection, account_id: str) -> dict[str, int]:
    """Que hay detras de una cuenta. Es lo que decide si se puede cerrar y ya."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT (SELECT count(*) FROM fincilia.canonical_movement "
            "         WHERE financial_account_id = %s) AS movements, "
            "       (SELECT count(*) FROM fincilia.data_source_account "
            "         WHERE financial_account_id = %s AND status = 'active') AS links",
            (account_id, account_id))
        row = _one(cursor) or {}
    return {"movements": int(row.get("movements", 0)),
            "links": int(row.get("links", 0))}


# --------------------------------------------------------------------------- #
# Fuentes
# --------------------------------------------------------------------------- #

def create_source(connection: psycopg.Connection, *, company_id: str,
                  source_family: str, display_name: str, purpose_code: str,
                  timezone: str) -> dict[str, Any]:
    _check_common(display_name=display_name, timezone=timezone)
    if source_family not in SOURCE_FAMILIES:
        raise OnboardingError("invalid-family",
                              f"{source_family!r} is not a source family")
    if not 3 <= len(purpose_code.strip()) <= 64:
        raise OnboardingError("invalid-purpose",
                              "the purpose code is between 3 and 64 characters")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_source_id FROM fincilia.data_source "
            "WHERE company_id = %s AND display_name = %s",
            (company_id, display_name.strip()))
        if cursor.fetchone() is not None:
            raise OnboardingError(
                "source-already-exists",
                "this company already has a source with that name; two sources "
                "that look the same are two sources nobody can tell apart")
        cursor.execute(
            "INSERT INTO fincilia.data_source (data_source_id, company_id, "
            "source_family, display_name, purpose_code, timezone) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s) "
            "RETURNING data_source_id, source_family, display_name, purpose_code, "
            "          timezone, status, created_at",
            (company_id, source_family, display_name.strip(),
             purpose_code.strip(), timezone))
        return _stamp(_one(cursor) or {})


def list_sources(connection: psycopg.Connection, *,
                 include_inactive: bool = True) -> list[dict[str, Any]]:
    statement = (
        "SELECT data_source_id, source_family, display_name, purpose_code, "
        "       timezone, status, closed_reason, created_at, updated_at "
        "FROM fincilia.data_source ")
    if not include_inactive:
        statement += "WHERE status = 'active' "
    statement += "ORDER BY display_name"
    with connection.cursor() as cursor:
        cursor.execute(statement)
        return [_stamp(row) for row in _all(cursor)]


def load_source(connection: psycopg.Connection,
                data_source_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data_source_id, source_family, display_name, purpose_code, "
            "       timezone, status, closed_reason, created_at, updated_at "
            "FROM fincilia.data_source WHERE data_source_id = %s", (data_source_id,))
        row = _one(cursor)
    return _stamp(row) if row else None


def update_source(connection: psycopg.Connection, *, data_source_id: str,
                  display_name: str | None = None, purpose_code: str | None = None,
                  timezone: str | None = None, status: str | None = None,
                  closed_reason: str | None = None) -> dict[str, Any]:
    current = load_source(connection, data_source_id)
    if current is None:
        raise OnboardingError("source-unknown", "no such data source")
    if display_name is not None or timezone is not None:
        _check_common(display_name=display_name or current["display_name"],
                      timezone=timezone or current["timezone"])
    if status is not None and status not in LIFECYCLE:
        raise OnboardingError("invalid-status", f"{status!r} is not a lifecycle state")
    if status is not None and status != "active" and not (closed_reason or "").strip():
        raise OnboardingError("reason-required",
                              "suspending or closing a source carries its reason")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.data_source SET "
            "  display_name = coalesce(%s, display_name), "
            "  purpose_code = coalesce(%s, purpose_code), "
            "  timezone = coalesce(%s, timezone), "
            "  status = coalesce(%s, status), "
            "  closed_reason = CASE WHEN coalesce(%s, status) = 'active' "
            "                       THEN NULL ELSE %s END, "
            "  updated_at = now() WHERE data_source_id = %s "
            "RETURNING data_source_id, source_family, display_name, purpose_code, "
            "          timezone, status, closed_reason, updated_at",
            (display_name.strip() if display_name else None,
             purpose_code.strip() if purpose_code else None, timezone, status,
             status, (closed_reason or "").strip() or None, data_source_id))
        return _stamp(_one(cursor) or {})


# --------------------------------------------------------------------------- #
# Vinculos
# --------------------------------------------------------------------------- #

def link_account(connection: psycopg.Connection, *, company_id: str,
                 data_source_id: str, financial_account_id: str,
                 relation_role: str, subject_id: str,
                 valid_from: date | None = None) -> dict[str, Any]:
    """Vincula una fuente con una cuenta, con el papel que juega.

    Una fuente se relaciona con **varias** cuentas: una pasarela liquida a una
    cuenta bancaria y concilia contra un libro contable. Por eso el papel es
    parte del vinculo y no una propiedad de la fuente.
    """
    if relation_role not in RELATION_ROLES:
        raise OnboardingError("invalid-role",
                              f"{relation_role!r} is not a relation role")
    account = load_account(connection, financial_account_id)
    source = load_source(connection, data_source_id)
    if account is None or source is None:
        # Indistinguible de «no existe»: una respuesta que separara las dos cosas
        # convertiria esto en un buscador de cuentas ajenas.
        raise OnboardingError("link-refused",
                              "the source or the account is not available here")
    if account["status"] != "active" or source["status"] != "active":
        raise OnboardingError(
            "link-inactive",
            "a suspended or closed source or account does not take new links")

    with connection.cursor() as cursor:
        try:
            with connection.transaction():
                cursor.execute(
                    "INSERT INTO fincilia.data_source_account (link_id, company_id, "
                    "data_source_id, financial_account_id, relation_role, "
                    "valid_from, created_by) VALUES (gen_random_uuid(), %s, %s, %s, "
                    "%s, coalesce(%s, CURRENT_DATE), %s) "
                    "RETURNING link_id, data_source_id, financial_account_id, "
                    "          relation_role, valid_from, valid_to, status, created_at",
                    (company_id, data_source_id, financial_account_id,
                     relation_role, valid_from, subject_id))
                return _stamp(_one(cursor) or {})
        except psycopg.errors.UniqueViolation as error:
            if "uq_source_account_primary" in str(error):
                raise OnboardingError(
                    "primary-already-set",
                    "this source already settles into a primary account; retire "
                    "that link before naming another, or use a different role"
                ) from None
            raise OnboardingError(
                "link-already-exists",
                "this source and account are already linked with that role") from None


def list_links(connection: psycopg.Connection, *,
               data_source_id: str | None = None) -> list[dict[str, Any]]:
    statement = (
        "SELECT l.link_id, l.data_source_id, l.financial_account_id, "
        "       l.relation_role, l.valid_from, l.valid_to, l.status, "
        "       s.display_name AS source_name, a.display_name AS account_name, "
        "       a.currency_code, a.identifier_last4, a.status AS account_status "
        "FROM fincilia.data_source_account l "
        "JOIN fincilia.data_source s ON s.data_source_id = l.data_source_id "
        "JOIN fincilia.financial_account a "
        "     ON a.account_id = l.financial_account_id ")
    params: tuple = ()
    if data_source_id:
        statement += "WHERE l.data_source_id = %s "
        params = (data_source_id,)
    statement += "ORDER BY s.display_name, l.relation_role"
    with connection.cursor() as cursor:
        cursor.execute(statement, params)
        return [_stamp(row) for row in _all(cursor)]


def retire_link(connection: psycopg.Connection, *, link_id: str,
                status: str) -> dict[str, Any]:
    """Retira un vinculo. **No lo borra**: dejo de valer, no dejo de existir."""
    if status not in ("suspended", "closed"):
        raise OnboardingError("invalid-status",
                              "a link is retired by suspending or closing it")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.data_source_account SET status = %s, "
            "  valid_to = coalesce(valid_to, CURRENT_DATE) WHERE link_id = %s "
            "RETURNING link_id, data_source_id, financial_account_id, "
            "          relation_role, valid_from, valid_to, status",
            (status, link_id))
        row = _one(cursor)
    if row is None:
        raise OnboardingError("link-unknown", "no such link")
    return _stamp(row)


# --------------------------------------------------------------------------- #
# Ciclos y expectativas
# --------------------------------------------------------------------------- #

def set_cycle(connection: psycopg.Connection, *, company_id: str,
              data_source_id: str, periodicity: str, custom_days: int | None,
              due_day_offset: int, grace_days: int, responsible_subject_id: str,
              timezone: str, anchor: date, subject_id: str) -> dict[str, Any]:
    """Declara cada cuanto se espera un documento de esta fuente.

    Solo hay un ciclo vivo por fuente. Cambiarlo retira el anterior en vez de
    editarlo: las expectativas que ya generó siguen apuntando a las reglas con
    las que se generaron, y reescribirlas cambiaria si algo llego tarde.
    """
    problems = validate_cycle(periodicity, custom_days, due_day_offset, grace_days)
    if problems:
        raise OnboardingError("invalid-cycle", "; ".join(problems))
    if timezone not in TIMEZONES:
        raise OnboardingError("invalid-timezone", f"{timezone!r} is not supported")
    if load_source(connection, data_source_id) is None:
        raise OnboardingError("source-unknown", "no such data source")
    # Un responsable que ya no puede entrar a la empresa no puede recibir una
    # tarea en ella. Se comprueba al asignar y no solo al pintar el desplegable:
    # el desplegable es una comodidad, y esto es la regla.
    if not is_eligible(connection, responsible_subject_id):
        raise OnboardingError(
            "assignee-not-eligible",
            "that person is not an active member with a live grant on this "
            "company, so they cannot answer for anything here")

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.source_cycle SET status = 'closed', updated_at = now() "
            "WHERE data_source_id = %s AND status = 'active'", (data_source_id,))
        cursor.execute(
            "INSERT INTO fincilia.source_cycle (cycle_id, company_id, "
            "data_source_id, periodicity, custom_days, due_day_offset, grace_days, "
            "responsible_subject_id, timezone, anchor_date, created_by) "
            "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "RETURNING cycle_id, data_source_id, periodicity, custom_days, "
            "          due_day_offset, grace_days, responsible_subject_id, "
            "          timezone, anchor_date, status, created_at",
            (company_id, data_source_id, periodicity, custom_days, due_day_offset,
             grace_days, responsible_subject_id, timezone, anchor, subject_id))
        return _stamp(_one(cursor) or {})


def load_cycle(connection: psycopg.Connection,
               data_source_id: str) -> dict[str, Any] | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT cycle_id, data_source_id, periodicity, custom_days, "
            "       due_day_offset, grace_days, responsible_subject_id, timezone, "
            "       anchor_date, status, created_at FROM fincilia.source_cycle "
            "WHERE data_source_id = %s AND status = 'active'", (data_source_id,))
        row = _one(cursor)
    if row is None:
        return None
    cycle = _stamp(row)
    # Revocar a alguien **no** borra el ciclo: la historia se conserva y lo que
    # cambia es que queda pendiente de reemplazo. Borrarlo dejaria la fuente sin
    # calendario justo el dia que alguien se fue.
    cycle["responsible_eligible"] = is_eligible(
        connection, cycle["responsible_subject_id"])
    return cycle


def generate_expectations(connection: psycopg.Connection, *, company_id: str,
                          data_source_id: str, until: date) -> dict[str, int]:
    """Materializa los periodos del ciclo hasta una fecha. Idempotente.

    `until` entra como argumento y no sale del reloj: generar dos veces el mismo
    horizonte tiene que producir lo mismo, y un generador que mirara la hora
    produciria un periodo mas cada mes sin que nadie lo pidiera.
    """
    cycle = load_cycle(connection, data_source_id)
    if cycle is None:
        raise OnboardingError(
            "cycle-missing",
            "this source has no expected cycle; without one there is no date to "
            "be late against")
    try:
        periods = periods_between(
            anchor=date.fromisoformat(cycle["anchor_date"]), until=until,
            periodicity=cycle["periodicity"], custom_days=cycle["custom_days"],
            due_day_offset=cycle["due_day_offset"], grace_days=cycle["grace_days"])
    except CycleError as error:
        raise OnboardingError("invalid-cycle", str(error)) from None

    account = None
    links = [item for item in list_links(connection, data_source_id=data_source_id)
             if item["relation_role"] == "primary" and item["status"] == "active"]
    if links:
        account = links[0]["financial_account_id"]

    created = 0
    with connection.cursor() as cursor:
        for period in periods:
            cursor.execute(
                "INSERT INTO fincilia.source_expectation (expectation_id, "
                "company_id, data_source_id, financial_account_id, cycle_id, "
                "period_start, period_end, due_on, late_after) "
                "VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (data_source_id, period_start, period_end) DO NOTHING",
                (company_id, data_source_id, account, cycle["cycle_id"],
                 period.period_start, period.period_end, period.due_on,
                 period.late_after))
            created += cursor.rowcount
    return {"periods": len(periods), "created": created}


def list_expectations(connection: psycopg.Connection, *, today: date,
                      data_source_id: str | None = None,
                      limit: int = 100) -> list[dict[str, Any]]:
    """Las expectativas y su estado el dia `today`.

    El estado se calcula al leer y **no** se guarda al vuelo: guardarlo obligaria
    a un proceso que pasara cada noche marcando atrasos, y un dia que ese proceso
    no corriera nada estaria atrasado.
    """
    statement = (
        "SELECT e.expectation_id, e.data_source_id, e.financial_account_id, "
        "       e.period_start, e.period_end, e.due_on, e.late_after, e.state, "
        "       e.satisfied_by, e.satisfied_at, e.waived_reason, "
        "       s.display_name AS source_name FROM fincilia.source_expectation e "
        "JOIN fincilia.data_source s ON s.data_source_id = e.data_source_id ")
    params: tuple = ()
    if data_source_id:
        statement += "WHERE e.data_source_id = %s "
        params = (data_source_id,)
    statement += "ORDER BY e.due_on DESC LIMIT %s"
    with connection.cursor() as cursor:
        cursor.execute(statement, params + (max(1, min(int(limit), 500)),))
        rows = _all(cursor)

    result = []
    for row in rows:
        stamped = _stamp(row)
        stored = row["state"]
        if stored == "pending" and today > row["late_after"]:
            stamped["state"] = "late"
            stamped["days_late"] = (today - row["late_after"]).days
        else:
            stamped["days_late"] = 0
        stamped["stored_state"] = stored
        result.append(stamped)
    return result


def satisfy_expectation(connection: psycopg.Connection, *, data_source_id: str,
                        artifact_id: str, uploaded_on: date) -> str | None:
    """Marca satisfecho el periodo al que corresponde un documento subido.

    Se elige el periodo abierto cuyo plazo esta mas cerca de la fecha de subida.
    Adivinar el periodo por el contenido del fichero seria interpretar antes de
    mapear, que es justo lo que este producto se niega a hacer.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE fincilia.source_expectation SET state = 'satisfied', "
            "  satisfied_by = %s, satisfied_at = now() "
            "WHERE expectation_id = ("
            "  SELECT expectation_id FROM fincilia.source_expectation "
            "   WHERE data_source_id = %s AND state = 'pending' "
            "     AND period_start <= %s "
            "   ORDER BY due_on DESC LIMIT 1) "
            "RETURNING expectation_id",
            (artifact_id, data_source_id, uploaded_on))
        row = cursor.fetchone()
    return str(row[0]) if row else None


# --------------------------------------------------------------------------- #
# Quien puede responder de un ciclo (FNC-P3.6)
# --------------------------------------------------------------------------- #

def eligible_assignees(connection: psycopg.Connection) -> list[dict[str, Any]]:
    """Personas que pueden recibir la responsabilidad de un ciclo en esta empresa.

    Las **mismas tres condiciones** que usa el autorizador para dejar entrar, y
    no una lista parecida escrita aparte: delegacion viva de una firma sobre la
    empresa, membresia activa del sujeto **en esa firma**, y al menos una
    concesion sin revocar. Dos definiciones de «quien puede» acaban discrepando,
    y la que discrepa siempre es la que nadie mira.

    Que la membresia se una a la firma **del engagement** tiene una consecuencia
    que importa: si la empresa cambia de firma, los miembros de la anterior dejan
    de ser elegibles el mismo dia, sin que nadie tenga que acordarse de limpiar
    nada.

    Sale el identificador opaco, el nombre visible y los roles **en esta
    empresa**. Ni correo, ni vinculo externo, ni credencial, ni en que otras
    firmas milita: un selector de responsables no es un directorio de personas.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT s.subject_id, s.display_name, "
            "       array_agg(DISTINCT g.company_role ORDER BY g.company_role) "
            "FROM fincilia.company_grant g "
            "JOIN fincilia.subject s ON s.subject_id = g.subject_id "
            "JOIN fincilia.engagement e ON e.company_id = g.company_id "
            "JOIN fincilia.membership m ON m.firm_id = e.firm_id "
            "                          AND m.subject_id = g.subject_id "
            "WHERE g.revoked_at IS NULL "
            "  AND e.status = 'active' "
            "  AND (e.valid_to IS NULL OR e.valid_to >= CURRENT_DATE) "
            "  AND m.status = 'active' "
            # Un principal de servicio no responde de que llegue un extracto.
            "  AND s.subject_kind = 'person' "
            "GROUP BY s.subject_id, s.display_name "
            "ORDER BY s.display_name")
        return [{"subject_id": str(row[0]), "display_name": row[1],
                 "company_roles": list(row[2])} for row in cursor]


def is_eligible(connection: psycopg.Connection, subject_id: str) -> bool:
    """Si **este** sujeto sigue pudiendo recibir tareas en esta empresa."""
    return any(item["subject_id"] == subject_id
               for item in eligible_assignees(connection))
