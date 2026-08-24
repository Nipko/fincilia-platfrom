"""Proyeccion read-only de candidatos de conciliacion.

Un candidato no es un match ni una decision. Esta consulta conserva esa
distancia deliberadamente: no persiste nada, no asigna puntajes y no consume
tolerancias monetarias. Los pares salen de reglas exactas y explicables sobre
dos datasets que ya pasaron los gates de completitud y linaje.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg


MAX_CANDIDATE_LIMIT = 200
MAX_CANDIDATE_OFFSET = 10_000
MAX_DATE_WINDOW_DAYS = 31
DEFAULT_CANDIDATE_LIMIT = 50
DEFAULT_DATE_WINDOW_DAYS = 3

ELIGIBLE_DATASET_STATES = frozenset(("validated", "published"))
ELIGIBLE_COMPLETENESS_STATES = frozenset(("verified", "accepted_exception"))

RULES = (
    "exact_amount",
    "same_currency",
    "opposite_direction",
    "different_financial_account",
    "date_within_explicit_window",
)


class CandidateQueryError(Exception):
    """La solicitud no define una exploracion segura y acotada."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CandidateQuery:
    left_dataset_id: str
    right_dataset_id: str
    max_days: int = DEFAULT_DATE_WINDOW_DAYS
    offset: int = 0
    limit: int = DEFAULT_CANDIDATE_LIMIT

    def validated(self) -> "CandidateQuery":
        if self.left_dataset_id == self.right_dataset_id:
            raise CandidateQueryError(
                "datasets-must-differ", "two distinct datasets are required")
        if not 0 <= self.max_days <= MAX_DATE_WINDOW_DAYS:
            raise CandidateQueryError(
                "date-window-invalid", "max_days must be between 0 and 31")
        if not 0 <= self.offset <= MAX_CANDIDATE_OFFSET:
            raise CandidateQueryError(
                "candidate-offset-invalid", "offset must be between 0 and 10000")
        if not 1 <= self.limit <= MAX_CANDIDATE_LIMIT:
            raise CandidateQueryError(
                "candidate-limit-invalid", "limit must be between 1 and 200")
        return self


def _dataset_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "dataset_version_id": str(row[0]),
        "state": row[1],
        "completeness_state": row[2],
        "lineage_state": row[3],
        "movement_count": int(row[4]),
    }


def _movement(values: tuple[Any, ...], start: int) -> dict[str, Any]:
    return {
        "movement_id": str(values[start]),
        # El adaptador entrega Decimal. Punto fijo y string impiden que JSON lo
        # convierta en float justo donde una aproximacion no es aceptable.
        "amount": f"{values[start + 1]:.12f}",
        "currency": values[start + 2],
        "direction": values[start + 3],
        "description": values[start + 4],
        "reference": values[start + 5],
        "occurred_on": values[start + 6].isoformat(),
        "state": values[start + 7],
        "record_ordinal": int(values[start + 8]),
    }


def candidate_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convierte una fila SQL sin interpretar dinero ni calcular afinidad."""
    reference_match = bool(row[19])
    signals = list(RULES)
    if reference_match:
        signals.append("same_normalised_reference")
    return {
        "left": _movement(row, 0),
        "right": _movement(row, 9),
        "date_distance_days": int(row[18]),
        "signals": signals,
    }


def _load_eligible_pair(connection: psycopg.Connection,
                        query: CandidateQuery) -> tuple[dict[str, Any], dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT dataset_version_id, state, completeness_state, lineage_state, "
            "       movement_count "
            "FROM fincilia.dataset_version "
            "WHERE dataset_version_id = ANY(%s::uuid[])",
            ([query.left_dataset_id, query.right_dataset_id],))
        found = {_dataset_row(row)["dataset_version_id"]: _dataset_row(row)
                 for row in cursor}

    # La misma respuesta cubre inexistente, otra empresa y no elegible. Revelar
    # cual de las tres condiciones ocurrio seria un oraculo de existencia.
    if set(found) != {query.left_dataset_id, query.right_dataset_id}:
        raise CandidateQueryError(
            "candidate-scope-unavailable",
            "the requested datasets are unavailable for candidate exploration")

    left = found[query.left_dataset_id]
    right = found[query.right_dataset_id]
    for dataset in (left, right):
        if (dataset["state"] not in ELIGIBLE_DATASET_STATES
                or dataset["completeness_state"] not in ELIGIBLE_COMPLETENESS_STATES
                or dataset["lineage_state"] != "complete"):
            raise CandidateQueryError(
                "candidate-scope-unavailable",
                "the requested datasets are unavailable for candidate exploration")
    return left, right


def explore_candidates(connection: psycopg.Connection, *,
                       left_dataset_id: str, right_dataset_id: str,
                       max_days: int = DEFAULT_DATE_WINDOW_DAYS,
                       offset: int = 0,
                       limit: int = DEFAULT_CANDIDATE_LIMIT) -> dict[str, Any]:
    """Compara dos datasets autorizados en SQL y devuelve una pagina estable."""
    query = CandidateQuery(
        left_dataset_id=left_dataset_id,
        right_dataset_id=right_dataset_id,
        max_days=int(max_days), offset=int(offset), limit=int(limit)).validated()
    left_dataset, right_dataset = _load_eligible_pair(connection, query)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT l.movement_id, l.amount, l.currency_code, l.direction, "
            "       l.description, l.reference_original, l.occurred_on, l.state, "
            "       lr.record_ordinal, "
            "       r.movement_id, r.amount, r.currency_code, r.direction, "
            "       r.description, r.reference_original, r.occurred_on, r.state, "
            "       rr.record_ordinal, "
            "       abs(l.occurred_on - r.occurred_on) AS date_distance_days, "
            "       (l.reference_normalised IS NOT NULL AND "
            "        l.reference_normalised = r.reference_normalised) AS reference_match "
            "FROM fincilia.canonical_movement l "
            "JOIN fincilia.source_record ls ON ls.source_record_id = l.source_record_id "
            "JOIN fincilia.raw_record lr ON lr.raw_record_id = ls.raw_record_id "
            "JOIN fincilia.canonical_movement r "
            "  ON r.dataset_version_id = %s "
            " AND r.amount = l.amount "
            " AND r.currency_code = l.currency_code "
            " AND r.direction <> l.direction "
            " AND r.financial_account_id <> l.financial_account_id "
            " AND abs(l.occurred_on - r.occurred_on) <= %s "
            " AND r.state IN ('proposed', 'confirmed') "
            " AND r.lineage_state = 'complete' "
            "JOIN fincilia.source_record rs ON rs.source_record_id = r.source_record_id "
            "JOIN fincilia.raw_record rr ON rr.raw_record_id = rs.raw_record_id "
            "WHERE l.dataset_version_id = %s "
            "  AND l.state IN ('proposed', 'confirmed') "
            "  AND l.lineage_state = 'complete' "
            "ORDER BY reference_match DESC, date_distance_days, "
            "         lr.record_ordinal, rr.record_ordinal, l.movement_id, r.movement_id "
            "LIMIT %s OFFSET %s",
            (query.right_dataset_id, query.max_days, query.left_dataset_id,
             query.limit + 1, query.offset))
        rows = list(cursor)

    truncated = len(rows) > query.limit
    candidates = [candidate_from_row(row) for row in rows[:query.limit]]
    return {
        "mode": "candidate_only",
        "proves_balance_reconciliation": False,
        "rules": list(RULES),
        "reference_role": "explanatory_order_only",
        "max_days": query.max_days,
        "offset": query.offset,
        "limit": query.limit,
        "truncated": truncated,
        "left_dataset": left_dataset,
        "right_dataset": right_dataset,
        "candidates": candidates,
    }
