"""Filas canonizables de facturas DIAN y extractos MT940. Solo biblioteca estandar.

ADR-039 §5 (FNC-SMB-002). `dian_invoice` y `mt940` leen el documento entero;
este modulo lo convierte en las mismas filas que produce cualquier otra
extraccion: un registro de cabecera y un registro por hecho, cada uno con su
localizador de origen. Asi el mapeo, la vista previa, el dataset y el linaje no
necesitan un camino aparte.

Reglas:

1. **Nada se inventa.** Cada celda sale de un elemento o de una etiqueta del
   documento, y el localizador lo nombra campo por campo (`field_paths` para
   XML, `field_tags`/`field_lines` para MT940). La unica celda compuesta es
   `descripcion`, y su linaje enumera todos los elementos que la forman.
2. **La cabecera es sintetica y lo dice.** Las columnas las fija este modulo,
   no el documento; su registro lleva `synthetic_header: true` y ningun valor
   del fichero.
3. **Parcial no se disfraza.** Una factura `partial` o un extracto que no cuadra
   se extraen igual —la evidencia es la que es— pero el resumen lo declara en
   `source_status` y el dataset que salga de ahi nunca queda `verified`.
4. **Dinero como texto exacto.** Los importes viajan con `format_money`, en punto
   fijo, sin miles: el mapeo propuesto los lee con `decimal_format = dot`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Final, Iterator

from .dian_invoice import DianInvoice, parse_dian_invoice
from .money import format_money
from .mt940 import MT940Result, parse_mt940

DIAN_RELEASE: Final[str] = "fnc-dian-ubl-rows-0.1.0"
MT940_RELEASE: Final[str] = "fnc-mt940-rows-0.1.0"

DIAN_HEADER: Final[tuple[str, ...]] = (
    "numero_factura", "cufe", "fecha_emision", "fecha_vencimiento",
    "nit_cliente", "nombre_cliente", "valor_a_pagar", "moneda", "descripcion")
DIAN_FIELDS: Final[tuple[str, ...]] = (
    "invoice_number", "cufe", "issue_date", "due_date", "customer_nit",
    "customer_name", "payable_amount", "currency")

MT940_HEADER: Final[tuple[str, ...]] = (
    "fecha_valor", "fecha_asiento", "direccion", "valor", "moneda",
    "referencia_cliente", "referencia_banco", "tipo", "informacion",
    "descripcion", "cuenta")


@dataclass(frozen=True)
class StructuredRow:
    """Un registro con la misma interfaz que las filas de `extraction`."""

    record_ordinal: int
    values: tuple[str, ...]
    origin: dict[str, Any] = field(default_factory=dict)

    def locator(self, artifact_sha256: str) -> dict[str, Any]:
        return {**self.origin, "artifact_sha256": artifact_sha256,
                "record_ordinal": self.record_ordinal,
                "field_count": len(self.values)}


# --------------------------------------------------------------------------- #
# Factura DIAN
# --------------------------------------------------------------------------- #

def _invoice_cells(invoice: DianInvoice) -> tuple[tuple[str, ...], list[Any]]:
    values: list[str] = []
    paths: list[Any] = []
    for name in DIAN_FIELDS:
        item = invoice.fields.get(name)
        if item is None:
            values.append("")
            paths.append(None)
            continue
        rendered = item.rendered()
        values.append("" if rendered is None else str(rendered))
        paths.append(item.lineage["path"])
    # La descripcion compuesta solo existe si estan sus tres piezas: una
    # descripcion a medias se pareceria a una completa en el cruce.
    pieces = [invoice.fields.get(name)
              for name in ("invoice_number", "customer_name", "customer_nit")]
    if all(item is not None for item in pieces):
        number, name, nit = (str(item.value) for item in pieces)
        values.append(f"Factura {number} {name} NIT {nit}"[:500])
        paths.append([item.lineage["path"] for item in pieces])
    else:
        values.append("")
        paths.append(None)
    return tuple(values), paths


def invoice_rows(invoice: DianInvoice) -> Iterator[StructuredRow]:
    """Cabecera y una fila por factura. El linaje va campo a campo."""
    container = None
    first = next(iter(invoice.fields.values()), None)
    if first is not None:
        container = first.lineage.get("container")
    root_path = "/Invoice"
    header_origin: dict[str, Any] = {
        "locator_kind": "xml_element", "element_path": root_path,
        "element_ordinal": 1, "field_paths": [None] * len(DIAN_HEADER),
        "synthetic_header": True, "parser_release": DIAN_RELEASE}
    if container:
        header_origin["container"] = container
    yield StructuredRow(1, DIAN_HEADER, header_origin)
    values, paths = _invoice_cells(invoice)
    origin: dict[str, Any] = {
        "locator_kind": "xml_element", "element_path": root_path,
        "element_ordinal": 1, "field_paths": paths,
        "source_status": invoice.status, "parser_release": DIAN_RELEASE}
    if container:
        origin["container"] = container
    yield StructuredRow(2, values, origin)


def invoice_summary(invoice: DianInvoice, artifact_sha256: str) -> dict[str, Any]:
    digest = hashlib.sha256()
    for row in invoice_rows(invoice):
        digest.update("\x1f".join(row.values).encode("utf-8") + b"\x1e")
    return {
        "state": "complete", "truncated": False, "truncation_reason": None,
        "failed": False, "record_count": 2, "row_count": 1, "ragged_rows": 0,
        "bytes_read": 0, "object_digest": artifact_sha256,
        "record_digest": digest.hexdigest(),
        "effective_encoding": "xml-ubl-2.1", "delimiter": "",
        "header": list(DIAN_HEADER), "header_row": 1, "first_data_row": 2,
        "column_count": len(DIAN_HEADER), "artifact_sha256": artifact_sha256,
        "document_kind": "dian_invoice", "parser_release": DIAN_RELEASE,
        "source_status": invoice.status,
        # Codigo ISO declarado por el documento; no es un importe ni un dato
        # personal y es lo unico que el mapeo propuesto necesita del contenido.
        "currency": str(invoice.value("currency") or ""),
        "missing": list(invoice.missing),
        "finding_codes": sorted({item.code for item in invoice.findings}),
    }


def stream_invoice_rows(payload: bytes, *, artifact_sha256: str
                        ) -> tuple[Iterator[StructuredRow], dict[str, Any]]:
    invoice = parse_dian_invoice(payload)
    return invoice_rows(invoice), invoice_summary(invoice, artifact_sha256)


def invoice_currency(payload: bytes) -> str:
    return str(parse_dian_invoice(payload).value("currency") or "")


# --------------------------------------------------------------------------- #
# MT940
# --------------------------------------------------------------------------- #

def _statement_currency(statement) -> str:
    for balance in (statement.opening, statement.closing, statement.closing_available):
        if balance is not None:
            return balance.currency
    return ""


def mt940_rows(result: MT940Result) -> Iterator[StructuredRow]:
    """Cabecera y una fila por `:61:`, con `:86:`, `:25:` y saldo como linaje."""
    first_line = 1
    if result.statements:
        first = result.statements[0]
        if first.opening is not None:
            first_line = int(first.opening.lineage["line_number"])
    yield StructuredRow(1, MT940_HEADER, {
        "locator_kind": "mt940_tag", "statement_index": 1, "tag": "20",
        "line_number": max(1, first_line), "field_tags": [None] * len(MT940_HEADER),
        "information_lines": [], "synthetic_header": True,
        "parser_release": MT940_RELEASE})
    ordinal = 1
    for statement in result.statements:
        currency = _statement_currency(statement)
        currency_tag = (statement.opening.tag if statement.opening is not None
                        else (statement.closing.tag if statement.closing else None))
        for item in statement.transactions:
            ordinal += 1
            description = (item.information or item.supplementary
                           or " ".join(part for part in (item.type_code,
                                                         item.customer_reference)
                                       if part)).strip()
            description_tag = ("86" if item.information
                               else "61")
            values = (
                item.value_date, item.entry_date or "", item.direction,
                format_money(item.amount), currency, item.customer_reference,
                item.bank_reference, item.type_code, item.information,
                description[:500], statement.account)
            tags = ["61", "61" if item.entry_date else None, "61", "61",
                    currency_tag if currency else None,
                    "61" if item.customer_reference else None,
                    "61" if item.bank_reference else None, "61",
                    "86" if item.information else None,
                    description_tag if description else None,
                    "25" if statement.account else None]
            yield StructuredRow(ordinal, values, {
                "locator_kind": "mt940_tag",
                "statement_index": statement.index, "tag": "61",
                "line_number": int(item.lineage["line_number"]),
                "information_lines": list(item.lineage.get("information_lines", [])),
                "field_tags": tags, "source_status": statement.status,
                "parser_release": MT940_RELEASE})


def mt940_summary(result: MT940Result, artifact_sha256: str) -> dict[str, Any]:
    digest = hashlib.sha256()
    records = 0
    for row in mt940_rows(result):
        records += 1
        digest.update("\x1f".join(row.values).encode("utf-8") + b"\x1e")
    currencies = sorted({_statement_currency(item) for item in result.statements}
                        - {""})
    return {
        "state": "complete", "truncated": False, "truncation_reason": None,
        "failed": False, "record_count": records, "row_count": records - 1,
        "ragged_rows": 0, "bytes_read": 0, "object_digest": artifact_sha256,
        "record_digest": digest.hexdigest(), "effective_encoding": "mt940",
        "delimiter": "", "header": list(MT940_HEADER), "header_row": 1,
        "first_data_row": 2, "column_count": len(MT940_HEADER),
        "artifact_sha256": artifact_sha256, "document_kind": "mt940",
        "parser_release": MT940_RELEASE,
        # Un extracto que no cuadra se extrae, pero no es una fuente verificada.
        "source_status": result.status, "balance_check": result.balance_check,
        "currencies": currencies,
    }


def stream_mt940_rows(payload: bytes, *, artifact_sha256: str
                      ) -> tuple[Iterator[StructuredRow], dict[str, Any]]:
    result = parse_mt940(payload)
    return mt940_rows(result), mt940_summary(result, artifact_sha256)


# --------------------------------------------------------------------------- #
# Perfil y mapeo propuesto
# --------------------------------------------------------------------------- #

def structured_profile(header: tuple[str, ...], rows: list[StructuredRow],
                       kinds: dict[int, str]) -> dict[str, Any]:
    """Perfil de forma sin valores: tipos fijados por el formato, no inferidos."""
    data = [row for row in rows if not row.origin.get("synthetic_header")]
    columns = []
    for index, name in enumerate(header):
        cells = [row.values[index] for row in data if index < len(row.values)]
        filled = [value for value in cells if value]
        columns.append({
            "index": index, "header": name, "non_empty": len(filled),
            "empty": len(cells) - len(filled),
            "min_length": min((len(value) for value in filled), default=0),
            "max_length": max((len(value) for value in filled), default=0),
            "inferred_type": kinds.get(index, "text"), "type_confidence": 1.0,
            "ambiguous": False})
    return {"state": "complete", "encoding": "structured", "delimiter": "",
            "has_header": True, "row_count": len(data),
            "column_count": len(header), "ragged_rows": 0, "truncated": False,
            "needs_decision": [], "columns": columns,
            "effective_encoding": "structured"}


DIAN_KINDS: Final[dict[int, str]] = {2: "date_iso", 3: "date_iso", 6: "decimal_dot"}
MT940_KINDS: Final[dict[int, str]] = {0: "date_iso", 1: "date_iso", 3: "decimal_dot"}


def profile_invoice(payload: bytes) -> dict[str, Any]:
    rows = list(invoice_rows(parse_dian_invoice(payload)))
    return {**structured_profile(DIAN_HEADER, rows, DIAN_KINDS),
            "document_kind": "dian_invoice"}


def profile_mt940(payload: bytes) -> dict[str, Any]:
    rows = list(mt940_rows(parse_mt940(payload)))
    return {**structured_profile(MT940_HEADER, rows, MT940_KINDS),
            "document_kind": "mt940"}


def proposed_definition(summary: dict[str, Any]) -> dict[str, Any] | None:
    """Mapeo de un formato de estructura conocida, o `None` si no es seguro.

    La factura emitida es un cobro esperado: `valor_a_pagar` positivo se lee
    como entrada (`signed_amount`). El MT940 trae su direccion explicita. Sin una
    sola moneda declarada por el documento no hay propuesta: la moneda nunca se
    asume.
    """
    kind = summary.get("document_kind")
    if kind == "dian_invoice":
        currency = str(summary.get("currency") or "")
        if len(currency) != 3:
            return None
        return {
            "columns": {"occurred_on": 2, "description": 8, "reference": 0,
                        "amount": 6},
            "date_format": "iso", "decimal_format": "dot", "currency": currency,
            "direction_mode": "signed_amount", "header_row": 1,
            "first_data_row": 2, "ignored_columns": [1, 3, 4, 5, 7],
            "template": {"template_id": "dian-ubl-invoice", "version": 1,
                         "calibration": "format_specification"},
        }
    if kind == "mt940":
        currencies = list(summary.get("currencies") or [])
        if len(currencies) != 1:
            return None
        return {
            "columns": {"occurred_on": 0, "description": 9, "reference": 5,
                        "amount": 3, "direction": 2},
            "date_format": "iso", "decimal_format": "dot",
            "currency": currencies[0], "direction_mode": "explicit_direction",
            "header_row": 1, "first_data_row": 2,
            "ignored_columns": [1, 4, 6, 7, 8, 10],
            "template": {"template_id": "swift-mt940", "version": 1,
                         "calibration": "format_specification"},
        }
    return None
