"""Mapeo propuesto por plantilla bancaria o por formato conocido (FNC-SMB-002).

ADR-039 §5: si la exportacion del banco coincide de forma inequivoca con una
plantilla, o si el documento es una factura DIAN o un MT940 (estructura fijada
por su norma), el servidor propone el mapeo y puede crearlo sin que la persona
asigne columnas. Si la deteccion no es inequivoca, la respuesta lo dice y el
flujo manual de siempre sigue disponible. Nada aqui publica ni valida datos:
el mapeo nace en borrador y pasa por los mismos bloqueos que uno manual.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import psycopg

from fincilia_contracts.bank_templates import (MAX_HEADER_SCAN, MAX_SAMPLE_ROWS,
                                               TEMPLATES, find_header,
                                               propose_mapping)
from fincilia_contracts.structured_rows import proposed_definition

from . import datasets

STRUCTURED_KINDS = frozenset({"dian_invoice", "mt940"})


@dataclass(frozen=True)
class _Row:
    record_ordinal: int
    values: tuple[str, ...]


def _template_info(template_id: str) -> dict[str, Any]:
    for template in TEMPLATES:
        if template.template_id == template_id:
            return {"template_id": template.template_id, "bank": template.bank,
                    "product": template.product, "version": template.version,
                    "calibration": template.calibration,
                    "source_url": template.source_url,
                    "source": "bank_template"}
    return {}


def detect(connection: psycopg.Connection, *, artifact_id: str) -> dict[str, Any]:
    """Que propondria el servidor para este documento. No escribe nada.

    `status`: `ready` (hay definicion aplicable), `needs_review` (una plantilla
    encaja pero la muestra no se lee de una sola forma) o `not_detected`.
    """
    run = datasets.latest_run(connection, artifact_id, "extract")
    if run is None:
        return {"status": "not_extracted", "template": None, "definition": None,
                "findings": [], "manual_mapping_available": True}
    summary = run["result"] or {}
    kind = summary.get("document_kind")
    if kind in STRUCTURED_KINDS:
        definition = proposed_definition(summary)
        if definition is None:
            return {"status": "needs_review", "template": None, "definition": None,
                    "findings": ["currency_not_unique"],
                    "manual_mapping_available": True, "run_id": run["run_id"]}
        template = dict(definition["template"])
        template["source"] = "format_specification"
        template["source_status"] = summary.get("source_status")
        return {"status": "ready", "template": template, "definition": definition,
                "findings": [], "manual_mapping_available": True,
                "run_id": run["run_id"]}

    rows = [_Row(int(item["record_ordinal"]), tuple(str(v) for v in item["values"]))
            for item in _first_records(connection, run["run_id"])]
    match = find_header(rows)
    if match is None:
        return {"status": "not_detected", "template": None, "definition": None,
                "findings": [], "manual_mapping_available": True,
                "run_id": run["run_id"]}
    data = [row for row in rows if row.record_ordinal > match.header_row]
    proposal = propose_mapping(match, data)
    template = {**_template_info(match.template.template_id),
                "header_row": match.header_row}
    return {"status": proposal.status, "template": template,
            "definition": proposal.definition,
            "findings": list(proposal.findings),
            "manual_mapping_available": True, "run_id": run["run_id"]}


def _first_records(connection: psycopg.Connection, run_id: str) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT record_ordinal, raw_values FROM fincilia.raw_record "
            "WHERE processing_run_id = %s ORDER BY record_ordinal LIMIT %s",
            (run_id, MAX_HEADER_SCAN + MAX_SAMPLE_ROWS))
        return [{"record_ordinal": row[0], "values": row[1] or []}
                for row in cursor]


def template_display_name(template_id: str, data_source_id: str) -> str:
    # Una plantilla por fuente: el mismo banco en dos cuentas son dos fuentes y
    # el nombre unico por empresa no debe hacerlas chocar.
    return f"Plantilla {template_id} {data_source_id[:8]}"[:160]


def existing_template_mapping(connection: psycopg.Connection, *,
                              data_source_id: str,
                              display_name: str) -> str | None:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT mapping_id FROM fincilia.column_mapping "
            "WHERE data_source_id = %s AND display_name = %s",
            (data_source_id, display_name))
        row = cursor.fetchone()
    return None if row is None else str(row[0])
