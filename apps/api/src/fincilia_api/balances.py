"""Observaciones canonicas de saldo respaldadas por evidencia publicada.

La persona selecciona dos celdas de una fila ya publicada: importe y fecha. El
servidor decide empresa, cuenta, moneda, convenio decimal, convenio de fecha,
release y esquema. Registrar esa observacion no demuestra completitud ni
conciliacion; el linaje permanece pendiente hasta materializar el camino de
campo completo.
"""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg

from . import financial_lineage
from fincilia_contracts.mapping import MappingError, normalise_amount, parse_date
from fincilia_contracts.money import MoneyError, format_money, parse_money
from fincilia_contracts.release import digest_of


BALANCE_TYPES = frozenset({"opening", "closing", "running", "available", "ledger"})
DEFAULT_LIMIT = 100
MAX_LIMIT = 200
DEFAULT_EVIDENCE_LIMIT = 20
MAX_EVIDENCE_LIMIT = 50


@dataclass(frozen=True)
class BalanceError(Exception):
    code: str
    detail: str


def _bounded(value: int, *, maximum: int, code: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise BalanceError(code, "limit must be an integer") from None
    if parsed < 1 or parsed > maximum:
        raise BalanceError(code, f"limit must be between 1 and {maximum}")
    return parsed


def _balance_row(row: tuple[Any, ...], *, replayed: bool = False) -> dict[str, Any]:
    return {
        "balance_id": str(row[0]),
        "financial_account_id": str(row[1]),
        "account_name": row[2],
        "source_record_id": str(row[3]),
        "source_name": row[4],
        "record_ordinal": int(row[5]),
        "balance_type": row[6],
        "amount": format_money(row[7]),
        "currency_code": row[8],
        "as_of": row[9].isoformat(),
        "source_timezone": row[10],
        "amount_field_index": int(row[11]),
        "as_of_field_index": int(row[12]),
        "lineage_state": row[13],
        "created_at": row[14].isoformat(),
        "replayed": replayed,
        "proves_completeness": False,
        "proves_reconciliation": False,
    }


BALANCE_SELECT = (
    "SELECT b.balance_id, b.financial_account_id, a.display_name, "
    "       b.source_record_id, ds.display_name, r.record_ordinal, "
    "       b.balance_type, b.amount, b.currency_code, b.as_of, "
    "       b.source_timezone, b.amount_field_index, b.as_of_field_index, "
    "       b.lineage_state, b.created_at "
    "FROM fincilia.account_balance b "
    "JOIN fincilia.financial_account a "
    "  ON a.account_id = b.financial_account_id AND a.company_id = b.company_id "
    "JOIN fincilia.source_record s "
    "  ON s.source_record_id = b.source_record_id AND s.company_id = b.company_id "
    "JOIN fincilia.data_source ds "
    "  ON ds.data_source_id = s.data_source_id AND ds.company_id = s.company_id "
    "JOIN fincilia.raw_record r "
    "  ON r.raw_record_id = s.raw_record_id AND r.company_id = s.company_id "
)


def list_balances(connection: psycopg.Connection, *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    bounded = _bounded(limit, maximum=MAX_LIMIT, code="balance-limit-invalid")
    with connection.cursor() as cursor:
        cursor.execute(BALANCE_SELECT + "ORDER BY b.as_of DESC, b.created_at DESC LIMIT %s",
                       (bounded + 1,))
        rows = cursor.fetchall()
    truncated = len(rows) > bounded
    items = [_balance_row(row) for row in rows[:bounded]]
    return {
        "limit": bounded,
        "truncated": truncated,
        "items": items,
        "notice": (
            "observations_only; balances do not by themselves prove completeness, "
            "reconciliation or close readiness"
        ),
    }


def list_evidence(connection: psycopg.Connection,
                  *, limit: int = DEFAULT_EVIDENCE_LIMIT) -> dict[str, Any]:
    """Filas recientes elegibles y acotadas para preparar un saldo.

    Lleva valores porque es una vista de evidencia deliberada. La ruta exige
    `close.prepare` y solo existe con datos sinteticos; auditoria registra el
    conteo, nunca las celdas.
    """
    bounded = _bounded(limit, maximum=MAX_EVIDENCE_LIMIT,
                       code="balance-evidence-limit-invalid")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT s.source_record_id, d.dataset_version_id, ds.display_name, "
            "       m.financial_account_id, a.display_name, a.currency_code, "
            "       r.record_ordinal, r.raw_values, v.definition, ds.timezone "
            "FROM fincilia.source_record s "
            "JOIN fincilia.dataset_version d "
            "  ON d.dataset_version_id = s.dataset_version_id "
            " AND d.company_id = s.company_id "
            "JOIN fincilia.raw_record r "
            "  ON r.raw_record_id = s.raw_record_id AND r.company_id = s.company_id "
            "JOIN fincilia.column_mapping_version v "
            "  ON v.mapping_version_id = d.mapping_version_id "
            " AND v.company_id = d.company_id "
            "JOIN fincilia.canonical_movement m "
            "  ON m.source_record_id = s.source_record_id "
            " AND m.dataset_version_id = d.dataset_version_id "
            " AND m.company_id = s.company_id "
            "JOIN fincilia.financial_account a "
            "  ON a.account_id = m.financial_account_id AND a.company_id = m.company_id "
            "JOIN fincilia.data_source ds "
            "  ON ds.data_source_id = s.data_source_id AND ds.company_id = s.company_id "
            "JOIN fincilia.data_source_account l "
            "  ON l.data_source_id = s.data_source_id "
            " AND l.financial_account_id = m.financial_account_id "
            " AND l.company_id = s.company_id AND l.status = 'active' "
            "WHERE d.state = 'published' AND d.completeness_state = 'verified' "
            "  AND d.lineage_state = 'complete' "
            "  AND s.state = 'published' AND s.lineage_state = 'complete' "
            "ORDER BY s.created_at DESC, r.record_ordinal DESC LIMIT %s",
            (bounded + 1,))
        rows = cursor.fetchall()

    items = []
    for row in rows[:bounded]:
        definition = row[8] or {}
        columns = definition.get("columns") or {}
        labels = {int(index): str(name) for name, index in columns.items()
                  if isinstance(index, int) or str(index).isdigit()}
        values = list(row[7] or [])
        items.append({
            "source_record_id": str(row[0]),
            "dataset_version_id": str(row[1]),
            "source_name": row[2],
            "financial_account_id": str(row[3]),
            "account_name": row[4],
            "currency_code": row[5],
            "record_ordinal": int(row[6]),
            "source_timezone": row[9],
            "fields": [
                {"index": index, "label": labels.get(index, f"columna_{index + 1}"),
                 "value": str(value)}
                for index, value in enumerate(values)
            ],
        })
    return {"limit": bounded, "truncated": len(rows) > bounded, "items": items}


def _load_evidence(connection: psycopg.Connection, source_record_id: str) -> dict[str, Any]:
    try:
        normalised = str(uuid.UUID(source_record_id))
    except (TypeError, ValueError, AttributeError):
        raise BalanceError("balance-evidence-unavailable",
                           "the selected evidence is not available") from None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT s.source_record_id, s.company_id, s.data_source_id, "
            "       s.engine_release_id, s.canonical_schema_version, "
            "       r.raw_values, v.definition, m.financial_account_id, "
            "       a.currency_code, a.display_name, ds.display_name, ds.timezone "
            "FROM fincilia.source_record s "
            "JOIN fincilia.dataset_version d "
            "  ON d.dataset_version_id = s.dataset_version_id "
            " AND d.company_id = s.company_id "
            "JOIN fincilia.raw_record r "
            "  ON r.raw_record_id = s.raw_record_id AND r.company_id = s.company_id "
            "JOIN fincilia.column_mapping_version v "
            "  ON v.mapping_version_id = d.mapping_version_id "
            " AND v.company_id = d.company_id "
            "JOIN fincilia.canonical_movement m "
            "  ON m.source_record_id = s.source_record_id "
            " AND m.dataset_version_id = d.dataset_version_id "
            " AND m.company_id = s.company_id "
            "JOIN fincilia.financial_account a "
            "  ON a.account_id = m.financial_account_id AND a.company_id = m.company_id "
            "JOIN fincilia.data_source ds "
            "  ON ds.data_source_id = s.data_source_id AND ds.company_id = s.company_id "
            "WHERE s.source_record_id = %s "
            "  AND s.state = 'published' AND s.lineage_state = 'complete' "
            "  AND d.state = 'published' AND d.completeness_state = 'verified' "
            "  AND d.lineage_state = 'complete'",
            (normalised,))
        row = cursor.fetchone()
    if row is None:
        raise BalanceError("balance-evidence-unavailable",
                           "the selected evidence is not available")
    return {
        "source_record_id": str(row[0]), "company_id": str(row[1]),
        "data_source_id": str(row[2]), "engine_release_id": str(row[3]),
        "canonical_schema_version": row[4], "raw_values": list(row[5] or []),
        "definition": row[6] or {}, "financial_account_id": str(row[7]),
        "currency_code": row[8], "account_name": row[9],
        "source_name": row[10], "source_timezone": row[11],
    }


def create_balance(connection: psycopg.Connection, *, company_id: str,
                   subject_id: str, source_record_id: str, balance_type: str,
                   amount_field_index: int, as_of_field_index: int) -> dict[str, Any]:
    if balance_type not in BALANCE_TYPES:
        raise BalanceError("balance-type-invalid", "the balance type is not supported")
    if (isinstance(amount_field_index, bool) or isinstance(as_of_field_index, bool)
            or amount_field_index < 0 or as_of_field_index < 0):
        raise BalanceError("balance-field-invalid", "field indices must be non-negative")

    evidence = _load_evidence(connection, source_record_id)
    if evidence["company_id"] != company_id:
        raise BalanceError("balance-evidence-unavailable",
                           "the selected evidence is not available")
    values = evidence["raw_values"]
    if amount_field_index >= len(values) or as_of_field_index >= len(values):
        raise BalanceError("balance-field-invalid",
                           "the selected field does not exist in this evidence row")

    definition = evidence["definition"]
    decimal_format = str(definition.get("decimal_format", ""))
    date_format = str(definition.get("date_format", ""))
    try:
        amount = parse_money(normalise_amount(str(values[amount_field_index]),
                                              decimal_format))
        local_date = dt.date.fromisoformat(
            parse_date(str(values[as_of_field_index]), date_format))
        timezone = ZoneInfo(evidence["source_timezone"])
    except (MappingError, MoneyError, ValueError, ZoneInfoNotFoundError) as error:
        raise BalanceError("balance-field-unreadable",
                           "the selected cells cannot be read with the versioned mapping") from error

    # Un saldo de fecha se observa al final de ese dia en la zona original. El
    # instante UTC y la zona se conservan; no depende de la zona del contenedor.
    as_of = dt.datetime.combine(local_date, dt.time.max, timezone).astimezone(dt.timezone.utc)
    amount_text = format_money(amount)
    field_digests = {
        "amount": digest_of({"type": "money_decimal", "value": amount_text}),
        "as_of": digest_of({"type": "instant", "value": as_of.isoformat()}),
    }
    key_payload = {
        "company_id": company_id,
        "source_record_id": evidence["source_record_id"],
        "financial_account_id": evidence["financial_account_id"],
        "balance_type": balance_type,
        "amount": amount_text,
        "currency_code": evidence["currency_code"],
        "as_of": as_of.isoformat(),
        "amount_field_index": amount_field_index,
        "as_of_field_index": as_of_field_index,
        "engine_release_id": evidence["engine_release_id"],
        "canonical_schema_version": evidence["canonical_schema_version"],
    }
    observation_key = digest_of(key_payload)
    identity_key = digest_of({
        "company_id": company_id,
        "source_record_id": evidence["source_record_id"],
        "financial_account_id": evidence["financial_account_id"],
        "balance_type": balance_type,
        "as_of": as_of.isoformat(),
        "amount_field_index": amount_field_index,
        "as_of_field_index": as_of_field_index,
    })
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                       (identity_key,))
        cursor.execute(
            "SELECT balance_id, observation_key, lineage_state "
            "FROM fincilia.account_balance WHERE company_id=%s "
            "AND source_record_id=%s AND financial_account_id=%s "
            "AND balance_type=%s AND as_of=%s AND amount_field_index=%s "
            "AND as_of_field_index=%s",
            (company_id, evidence["source_record_id"],
             evidence["financial_account_id"], balance_type, as_of,
             amount_field_index, as_of_field_index))
        existing = cursor.fetchone()
        balance_id = str(existing[0]) if existing else str(uuid.uuid4())
        if existing is not None and existing[1] != observation_key:
            raise BalanceError(
                "balance-observation-conflict",
                "that evidence coordinate already carries another observation")
        try:
            if existing is None:
                with connection.transaction():
                    financial_lineage.materialize_balance(
                        cursor, company_id=company_id, subject_id=subject_id,
                        balance_id=balance_id,
                        source_record_id=evidence["source_record_id"],
                        amount_field_index=amount_field_index,
                        as_of_field_index=as_of_field_index,
                        field_digests=field_digests)
                    cursor.execute(
                        "INSERT INTO fincilia.account_balance (balance_id, company_id, "
                        "financial_account_id, source_record_id, balance_type, amount, "
                        "currency_code, as_of, source_timezone, amount_field_index, "
                        "as_of_field_index, field_digests, observation_key, prepared_by, "
                        "engine_release_id, canonical_schema_version, lineage_state) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                        "%s::jsonb, %s, %s, %s, %s, 'complete')",
                        (balance_id, company_id, evidence["financial_account_id"],
                         evidence["source_record_id"], balance_type, amount_text,
                         evidence["currency_code"], as_of, evidence["source_timezone"],
                         amount_field_index, as_of_field_index, json.dumps(field_digests),
                         observation_key, subject_id, evidence["engine_release_id"],
                         evidence["canonical_schema_version"]))
            elif existing[2] == "complete":
                cursor.execute(
                    "SELECT fincilia.financial_lineage_complete("
                    "'account_balance', %s, %s)", (company_id, balance_id))
                if not cursor.fetchone()[0]:
                    # Filas sinteticas creadas antes de V0031 pueden declarar
                    # `complete` sin nodos fisicos. Un replay exacto es el unico
                    # camino permitido para materializar la prueba faltante; no
                    # se cambia importe, fecha, identidad ni estado financiero.
                    with connection.transaction():
                        financial_lineage.materialize_balance(
                            cursor, company_id=company_id, subject_id=subject_id,
                            balance_id=balance_id,
                            source_record_id=evidence["source_record_id"],
                            amount_field_index=amount_field_index,
                            as_of_field_index=as_of_field_index,
                            field_digests=field_digests)
                        cursor.execute(
                            "SELECT fincilia.financial_lineage_complete("
                            "'account_balance', %s, %s)", (company_id, balance_id))
                        if not cursor.fetchone()[0]:
                            raise BalanceError(
                                "financial-lineage-input-incomplete",
                                "the replayed balance could not prove its evidence")
        except psycopg.errors.CheckViolation as error:
            if error.diag.constraint_name == "ck_account_balance_evidence_eligible":
                raise BalanceError("balance-evidence-unavailable",
                                   "the selected evidence is no longer eligible") from None
            raise
        except financial_lineage.LineageError as error:
            raise BalanceError(error.code, error.detail) from None

        replayed = existing is not None
        cursor.execute(
            BALANCE_SELECT +
            "WHERE b.company_id = %s AND b.source_record_id = %s "
            "  AND b.financial_account_id = %s AND b.balance_type = %s "
            "  AND b.as_of = %s AND b.amount_field_index = %s "
            "  AND b.as_of_field_index = %s",
            (company_id, evidence["source_record_id"], evidence["financial_account_id"],
             balance_type, as_of, amount_field_index, as_of_field_index))
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("account balance insert completed without a row")
        cursor.execute("SELECT observation_key FROM fincilia.account_balance "
                       "WHERE balance_id = %s", (row[0],))
        stored_key = cursor.fetchone()[0]
    if stored_key != observation_key:
        raise BalanceError("balance-observation-conflict",
                           "that evidence coordinate already carries another observation")
    return _balance_row(row, replayed=replayed)
