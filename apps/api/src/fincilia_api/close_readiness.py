"""Diagnostico company-scoped de evidencia previa a un cierre.

Este modulo no ejecuta, propone ni certifica un cierre. Reune metadatos ya
persistidos y falla cerrado ante cualquier evidencia ausente o condicional.
Los importes no se leen: un control de cierre no debe convertirse, por
accidente, en un informe financiero ni sumar monedas incompatibles.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Iterable

import psycopg


DEFAULT_LIMIT = 12
MAX_LIMIT = 24
MAX_EXPECTATIONS = 1_200


class CloseReadinessError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CloseReadinessQuery:
    limit: int = DEFAULT_LIMIT

    def validated(self) -> "CloseReadinessQuery":
        if not 1 <= self.limit <= MAX_LIMIT:
            raise CloseReadinessError(
                "close-readiness-limit-invalid",
                "limit must be between 1 and 24")
        return self


def _control(code: str, state: str, count: int, detail: str) -> dict[str, Any]:
    if state not in {"pass", "blocked", "unavailable"}:
        raise ValueError("invalid close-readiness control state")
    return {"code": code, "state": state, "count": int(count), "detail": detail}


def _blocker(code: str, count: int, detail: str) -> dict[str, Any]:
    return {"code": code, "count": int(count), "detail": detail}


def _row_source(row: tuple[Any, ...]) -> dict[str, Any]:
    dataset_id = str(row[8]) if row[8] is not None else None
    return {
        "expectation_id": str(row[0]),
        "data_source_id": str(row[1]),
        "source_name": row[2],
        "financial_account_id": str(row[3]) if row[3] is not None else None,
        "period_start": row[4].isoformat(),
        "period_end": row[5].isoformat(),
        "expectation_state": row[6],
        "satisfied_by_artifact_id": str(row[7]) if row[7] is not None else None,
        "dataset_version_id": dataset_id,
        "dataset_state": row[9],
        "completeness_state": row[10],
        "lineage_state": row[11],
        "rejected_count": int(row[12] or 0),
        "movement_count": int(row[13] or 0),
        "prepared_at": row[14].isoformat() if row[14] is not None else None,
        "selection_rule": (
            "published_then_validated_then_latest_for_satisfied_artifact"
            if dataset_id else "no_dataset_for_satisfied_artifact"),
    }


def _period_rows(connection: psycopg.Connection, limit: int) -> list[tuple[Any, ...]]:
    """Lee una ventana de periodos y su mejor evidencia de dataset.

    La consulta LATERAL evita escoger implicitamente el supuesto "ultimo".
    Publicado gana a validado y luego se desempata de forma estable.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT period_start, period_end "
            "FROM fincilia.source_expectation "
            "GROUP BY period_start, period_end "
            "ORDER BY period_end DESC, period_start DESC LIMIT %s",
            (limit,))
        periods = list(cursor)
        if not periods:
            return []

        pairs = ", ".join(["(%s::date, %s::date)"] * len(periods))
        parameters: list[dt.date] = []
        for period_start, period_end in periods:
            parameters.extend((period_start, period_end))
        cursor.execute(
            "SELECT e.expectation_id, e.data_source_id, s.display_name, "
            "       e.financial_account_id, e.period_start, e.period_end, "
            "       e.state, e.satisfied_by, chosen.dataset_version_id, "
            "       chosen.state, chosen.completeness_state, "
            "       chosen.lineage_state, chosen.rejected_count, "
            "       chosen.movement_count, chosen.prepared_at "
            "FROM fincilia.source_expectation e "
            "JOIN fincilia.data_source s "
            "  ON s.data_source_id = e.data_source_id "
            " AND s.company_id = e.company_id "
            "LEFT JOIN LATERAL ("
            "  SELECT d.dataset_version_id, d.state, d.completeness_state, "
            "         d.lineage_state, d.rejected_count, d.movement_count, "
            "         d.prepared_at "
            "  FROM fincilia.dataset_version d "
            "  WHERE d.artifact_id = e.satisfied_by "
            "  ORDER BY CASE d.state WHEN 'published' THEN 0 "
            "                         WHEN 'validated' THEN 1 ELSE 2 END, "
            "           d.prepared_at DESC, d.dataset_version_id DESC "
            "  LIMIT 1"
            ") chosen ON true "
            f"WHERE (e.period_start, e.period_end) IN ({pairs}) "
            "ORDER BY e.period_end DESC, e.period_start DESC, "
            "         s.display_name, e.expectation_id LIMIT %s",
            tuple(parameters) + (MAX_EXPECTATIONS + 1,))
        rows = list(cursor)
        if len(rows) > MAX_EXPECTATIONS:
            raise CloseReadinessError(
                "close-readiness-scope-too-large",
                "the selected periods contain more than 1200 expectations; "
                "reduce the period window")
        return rows


def _dataset_checks(connection: psycopg.Connection,
                    dataset_ids: list[str]) -> dict[str, dict[str, Any]]:
    checks = {
        dataset_id: {
            "missing_accounting_dates": 0,
            "open_candidate_ids": set(),
            "active_high_quality_ids": set(),
            "proposed_corrections": 0,
            "approved_unapplied_corrections": 0,
        }
        for dataset_id in dataset_ids
    }
    if not dataset_ids:
        return checks

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT dataset_version_id, count(*) "
            "FROM fincilia.canonical_movement "
            "WHERE dataset_version_id = ANY(%s::uuid[]) "
            "  AND accounting_date IS NULL "
            "GROUP BY dataset_version_id",
            (dataset_ids,))
        for dataset_id, count in cursor:
            checks[str(dataset_id)]["missing_accounting_dates"] = int(count)

        cursor.execute(
            "SELECT c.candidate_id, lm.dataset_version_id, rm.dataset_version_id "
            "FROM fincilia.match_candidate c "
            "JOIN fincilia.canonical_movement lm "
            "  ON lm.movement_id = c.left_movement_id "
            "JOIN fincilia.canonical_movement rm "
            "  ON rm.movement_id = c.right_movement_id "
            "LEFT JOIN fincilia.match_decision d "
            "  ON d.candidate_id = c.candidate_id "
            "WHERE d.decision_id IS NULL "
            "  AND (lm.dataset_version_id = ANY(%s::uuid[]) "
            "       OR rm.dataset_version_id = ANY(%s::uuid[]))",
            (dataset_ids, dataset_ids))
        for candidate_id, left_dataset_id, right_dataset_id in cursor:
            for dataset_id in {str(left_dataset_id), str(right_dataset_id)}:
                if dataset_id in checks:
                    checks[dataset_id]["open_candidate_ids"].add(str(candidate_id))

        cursor.execute(
            "SELECT q.issue_id, q.scope_kind, q.scope_ref, m.dataset_version_id "
            "FROM fincilia.quality_issue q "
            "LEFT JOIN fincilia.canonical_movement m "
            "  ON q.scope_kind = 'movement' AND m.movement_id = q.scope_ref "
            "WHERE q.status IN ('open', 'acknowledged') "
            "  AND q.severity = 'high' "
            "  AND ((q.scope_kind = 'dataset' "
            "        AND q.scope_ref = ANY(%s::uuid[])) "
            "       OR (q.scope_kind = 'movement' "
            "           AND m.dataset_version_id = ANY(%s::uuid[])))",
            (dataset_ids, dataset_ids))
        for issue_id, scope_kind, scope_ref, movement_dataset_id in cursor:
            dataset_id = (str(scope_ref) if scope_kind == "dataset"
                          else str(movement_dataset_id))
            if dataset_id in checks:
                checks[dataset_id]["active_high_quality_ids"].add(str(issue_id))

        cursor.execute(
            "SELECT o.dataset_version_id, "
            "       count(*) FILTER (WHERE r.review_id IS NULL), "
            "       count(*) FILTER (WHERE r.decision = 'approved' "
            "         AND ai.application_item_id IS NULL) "
            "FROM fincilia.field_overlay o "
            "LEFT JOIN fincilia.field_overlay_review r "
            "  ON r.overlay_id = o.overlay_id "
            "LEFT JOIN fincilia.field_overlay_application_item ai "
            "  ON ai.overlay_id = o.overlay_id "
            "WHERE o.dataset_version_id = ANY(%s::uuid[]) "
            "GROUP BY o.dataset_version_id",
            (dataset_ids,))
        for dataset_id, proposed, approved_unapplied in cursor:
            check = checks[str(dataset_id)]
            check["proposed_corrections"] = int(proposed)
            check["approved_unapplied_corrections"] = int(approved_unapplied)
    return checks


def _count_unique(checks: Iterable[dict[str, Any]], field: str) -> int:
    values: set[str] = set()
    for check in checks:
        values.update(check[field])
    return len(values)


def _build_period(period_start: dt.date, period_end: dt.date,
                  sources: list[dict[str, Any]],
                  dataset_checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    selected = [source for source in sources if source["dataset_version_id"]]
    checks = [dataset_checks[source["dataset_version_id"]] for source in selected]

    pending_expectations = sum(source["expectation_state"] != "satisfied"
                               for source in sources)
    missing_datasets = sum(source["dataset_version_id"] is None for source in sources)
    unpublished = sum(source["dataset_version_id"] is not None
                      and source["dataset_state"] != "published" for source in sources)
    incomplete = sum(source["dataset_version_id"] is not None
                     and source["completeness_state"] != "verified" for source in sources)
    lineage_gaps = sum(source["dataset_version_id"] is not None
                       and source["lineage_state"] != "complete" for source in sources)
    rejected_rows = sum(source["rejected_count"] for source in selected)
    missing_dates = sum(check["missing_accounting_dates"] for check in checks)
    open_reviews = _count_unique(checks, "open_candidate_ids")
    high_issues = _count_unique(checks, "active_high_quality_ids")
    pending_corrections = sum(
        check["proposed_corrections"] + check["approved_unapplied_corrections"]
        for check in checks)

    controls = [
        _control("expected_sources", "pass" if sources else "blocked", len(sources),
                 "Fuentes esperadas configuradas para el periodo."),
        _control("expectations_satisfied", "pass" if pending_expectations == 0 else "blocked",
                 pending_expectations, "Expectativas pendientes, tardias o exoneradas."),
        _control("dataset_evidence", "pass" if missing_datasets == 0 else "blocked",
                 missing_datasets, "Fuentes sin dataset asociado a su evidencia satisfecha."),
        _control("published_datasets", "pass" if unpublished == 0 else "blocked",
                 unpublished, "Datasets que aun no estan publicados."),
        _control("verified_completeness", "pass" if incomplete == 0 else "blocked",
                 incomplete, "Datasets sin completitud verificada."),
        _control("complete_lineage", "pass" if lineage_gaps == 0 else "blocked",
                 lineage_gaps, "Datasets cuyo linaje no esta completo."),
        _control("rejected_rows", "pass" if rejected_rows == 0 else "blocked",
                 rejected_rows, "Filas rechazadas que requieren explicacion."),
        _control("accounting_dates", "pass" if missing_dates == 0 else "blocked",
                 missing_dates, "Movimientos sin fecha contable."),
        _control("reconciliation_reviews", "pass" if open_reviews == 0 else "blocked",
                 open_reviews, "Expedientes de conciliacion sin decision humana."),
        _control("quality_alerts", "pass" if high_issues == 0 else "blocked",
                 high_issues, "Alertas de calidad altas abiertas o reconocidas."),
        _control("pending_corrections", "pass" if pending_corrections == 0 else "blocked",
                 pending_corrections, "Correcciones propuestas o aprobadas sin aplicar."),
        _control("account_balances", "unavailable", 1,
                 "El producto aun no materializa evidencia de saldo por cuenta y periodo."),
        _control("reconciliation_statements", "unavailable", 1,
                 "El producto aun no materializa un estado de conciliacion por periodo."),
        _control("product_close", "unavailable", 1,
                 "La ejecucion de cierre permanece fuera del alcance autorizado."),
    ]
    blockers = [
        _blocker(control["code"], control["count"], control["detail"])
        for control in controls if control["state"] != "pass"
    ]
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "status": "blocked",
        "close_ready": False,
        "can_execute_close": False,
        "source_count": len(sources),
        "selected_dataset_count": len(selected),
        "controls": controls,
        "blockers": blockers,
        "sources": sources,
    }


def list_close_readiness(connection: psycopg.Connection,
                         *, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Devuelve una evaluacion explicable sin habilitar ningun cierre."""
    query = CloseReadinessQuery(limit=int(limit)).validated()
    rows = _period_rows(connection, query.limit)
    sources = [_row_source(row) for row in rows]
    dataset_ids = sorted({source["dataset_version_id"] for source in sources
                          if source["dataset_version_id"]})
    checks = _dataset_checks(connection, dataset_ids)

    periods: dict[tuple[dt.date, dt.date], list[dict[str, Any]]] = {}
    for row, source in zip(rows, sources, strict=True):
        periods.setdefault((row[4], row[5]), []).append(source)
    items = [_build_period(start, end, period_sources, checks)
             for (start, end), period_sources in periods.items()]

    return {
        "mode": "diagnostic_only",
        "close_ready": False,
        "can_execute_close": False,
        "period_count": len(items),
        "blocked_period_count": len(items),
        "source_count": len(sources),
        "limit": query.limit,
        "items": items,
        "notice": (
            "diagnostic_only; no balance, certified reconciliation or close "
            "is calculated, asserted or executed"),
    }
