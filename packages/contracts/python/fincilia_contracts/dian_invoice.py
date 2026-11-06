"""Lectura segura de facturas electronicas DIAN (UBL 2.1). Solo biblioteca estandar.

ADR-039 §5: la factura emitida es la contraparte del extracto para responder
«quien me pago / que me falta cobrar». Este modulo la lee; no concilia nada.

Cuatro reglas ordenan el modulo:

1. **El XML subido es entrada no confiable.** Se rechaza cualquier DTD o
   declaracion de entidad antes de entregar los bytes al parser (XXE, billion
   laughs), se acotan tamano, profundidad y numero de elementos mientras se lee,
   y nunca se resuelve un recurso externo.
2. **Se lee por espacio de nombres, no por prefijo.** El prefijo `cbc:` lo elige
   quien genera el fichero; el URI es lo que dice que es UBL.
3. **El dinero es `Decimal` estricto.** Un importe con forma rara no se arregla:
   se deja sin valor, se explica y el resultado queda `partial`.
4. **Nada se adivina.** Un campo obligatorio ausente deja el resultado `partial`
   con la lista de lo que falta. `partial` nunca alimenta auto-match ni cierre.

Cada campo publicado lleva su linaje: ruta de etiquetas con ordinal entre
hermanos y ordinal del elemento en orden de documento. En un `AttachedDocument`
la ruta indica ademas el elemento contenedor de la factura embebida.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final

from .money import MoneyError, format_money, parse_money

# --------------------------------------------------------------------------- #
# Limites
# --------------------------------------------------------------------------- #

# Una factura DIAN real pesa decenas de kilobytes; cinco megas dejan margen para
# facturas con muchas lineas sin abrir la puerta a un documento hostil enorme.
MAX_XML_BYTES: Final[int] = 5 * 1024 * 1024
MAX_XML_DEPTH: Final[int] = 64
MAX_XML_ELEMENTS: Final[int] = 100_000
MAX_TEXT_LENGTH: Final[int] = 4_096
FEED_CHUNK: Final[int] = 64 * 1024

NS: Final[dict[str, str]] = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "att": "urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
PREFIX_OF: Final[dict[str, str]] = {
    NS["cac"]: "cac", NS["cbc"]: "cbc", NS["inv"]: "", NS["att"]: "",
}
INVOICE_ROOT: Final[str] = f"{{{NS['inv']}}}Invoice"
ATTACHED_ROOT: Final[str] = f"{{{NS['att']}}}AttachedDocument"
# Otros documentos UBL que la DIAN tambien emite. Se reconocen para decir con
# precision que no se leen, en vez de tratarlos como XML cualquiera.
OTHER_UBL_ROOTS: Final[frozenset[str]] = frozenset({
    "CreditNote", "DebitNote", "ApplicationResponse"})

REQUIRED_FIELDS: Final[tuple[str, ...]] = (
    "invoice_number", "cufe", "issue_date", "currency", "supplier_nit",
    "customer_nit", "payable_amount")
MONETARY_FIELDS: Final[dict[str, str]] = {
    "line_extension_amount": "LineExtensionAmount",
    "tax_exclusive_amount": "TaxExclusiveAmount",
    "tax_inclusive_amount": "TaxInclusiveAmount",
    "allowance_total_amount": "AllowanceTotalAmount",
    "charge_total_amount": "ChargeTotalAmount",
    "prepaid_amount": "PrepaidAmount",
    "payable_amount": "PayableAmount",
}
STRICT_AMOUNT = re.compile(r"^-?\d{1,26}(?:\.\d{1,12})?$")
STRICT_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
DANGEROUS_DECLARATIONS: Final[tuple[bytes, ...]] = (b"<!doctype", b"<!entity")


class DianInvoiceError(ValueError):
    """El documento no se puede leer con seguridad. `code` dice por que."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True)
class Finding:
    """Un motivo por el que algo quedo sin valor. Nunca repite el valor."""

    code: str
    location: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "detail": self.detail}


@dataclass(frozen=True)
class FieldValue:
    name: str
    value: Any
    lineage: dict[str, Any]

    def rendered(self) -> Any:
        return format_money(self.value) if isinstance(self.value, Decimal) else self.value

    def as_dict(self) -> dict[str, Any]:
        return {"value": self.rendered(), "lineage": dict(self.lineage)}


@dataclass(frozen=True)
class TaxLine:
    """Un total de impuesto (`tax`) o de retencion (`withholding`)."""

    kind: str
    scheme_id: str
    scheme_name: str
    amount: Decimal
    lineage: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "scheme_id": self.scheme_id,
                "scheme_name": self.scheme_name, "amount": format_money(self.amount),
                "lineage": dict(self.lineage)}


@dataclass(frozen=True)
class PaymentMeans:
    means_id: str
    means_code: str
    payment_ids: tuple[str, ...]
    due_date: str
    lineage: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"means_id": self.means_id, "means_code": self.means_code,
                "payment_ids": list(self.payment_ids), "due_date": self.due_date,
                "lineage": dict(self.lineage)}


@dataclass(frozen=True)
class DianInvoice:
    """Lo leido de una factura. `status` es `complete` o `partial`, nunca otro."""

    status: str
    document_kind: str
    fields: dict[str, FieldValue]
    taxes: tuple[TaxLine, ...]
    payment_means: tuple[PaymentMeans, ...]
    missing: tuple[str, ...]
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    def value(self, name: str) -> Any:
        item = self.fields.get(name)
        return None if item is None else item.value

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "document_kind": self.document_kind,
                "fields": {name: item.as_dict()
                           for name, item in sorted(self.fields.items())},
                "taxes": [item.as_dict() for item in self.taxes],
                "payment_means": [item.as_dict() for item in self.payment_means],
                "missing": list(self.missing),
                "findings": [item.as_dict() for item in self.findings]}

    def manifest(self) -> dict[str, Any]:
        """Forma sin valores: lo unico que puede vivir junto al metadato."""
        return {"document_kind": "dian_invoice", "ubl_root": self.document_kind,
                "status": self.status, "fields_present": sorted(self.fields),
                "missing": list(self.missing), "tax_lines": len(self.taxes),
                "finding_codes": sorted({item.code for item in self.findings})}


# --------------------------------------------------------------------------- #
# Parser acotado
# --------------------------------------------------------------------------- #

def looks_like_xml(head: bytes) -> bool:
    """Los primeros bytes son un documento XML (declaracion o elemento raiz)."""
    text = head.lstrip(b"\xef\xbb\xbf").lstrip()
    if text.startswith(b"<?xml"):
        return True
    return re.match(rb"<[A-Za-z_][\w.\-]*(?::[A-Za-z_][\w.\-]*)?[\s>/]", text) is not None


def reject_declarations(payload: bytes) -> None:
    # Quitar NUL permite reconocer la misma declaracion codificada en UTF-16.
    lowered = payload.lower().replace(b"\x00", b"")
    if any(token in lowered for token in DANGEROUS_DECLARATIONS):
        raise DianInvoiceError("unsafe_xml_declaration",
                               "the document declares a DTD or an entity")


def parse_bounded(payload: bytes, *, max_bytes: int = MAX_XML_BYTES,
                  max_depth: int = MAX_XML_DEPTH,
                  max_elements: int = MAX_XML_ELEMENTS) -> ET.Element:
    """Arbol XML con los limites comprobados **mientras** se lee, no despues."""
    if not payload:
        raise DianInvoiceError("malformed_xml", "an empty document")
    if len(payload) > max_bytes:
        raise DianInvoiceError("xml_too_large",
                               f"the document exceeds {max_bytes} bytes")
    reject_declarations(payload)
    parser = ET.XMLPullParser(events=("start", "end"))
    depth = 0
    elements = 0
    root: ET.Element | None = None
    try:
        for offset in range(0, len(payload), FEED_CHUNK):
            parser.feed(payload[offset:offset + FEED_CHUNK])
            for event, element in parser.read_events():
                if event == "start":
                    depth += 1
                    elements += 1
                    if root is None:
                        root = element
                    if depth > max_depth:
                        raise DianInvoiceError(
                            "xml_too_deep", f"nesting exceeds {max_depth} levels")
                    if elements > max_elements:
                        raise DianInvoiceError(
                            "too_many_elements",
                            f"the document exceeds {max_elements} elements")
                else:
                    depth -= 1
        parser.close()
        for _event, _element in parser.read_events():
            pass
    except ET.ParseError as error:
        raise DianInvoiceError("malformed_xml", "the document is not well formed") \
            from error
    if root is None:
        raise DianInvoiceError("malformed_xml", "the document has no root element")
    return root


def _local(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        uri, _, name = tag[1:].partition("}")
        return uri, name
    return "", tag


def _display(tag: str) -> str:
    uri, name = _local(tag)
    prefix = PREFIX_OF.get(uri, "ns" if uri else "")
    return f"{prefix}:{name}" if prefix else name


class _Index:
    """Ruta y ordinal de cada elemento, calculados una sola vez."""

    def __init__(self, root: ET.Element, container: str) -> None:
        self.container = container
        self.paths: dict[int, tuple[str, int]] = {}
        ordinal = 0
        stack: list[tuple[ET.Element, str]] = [(root, f"/{_display(root.tag)}")]
        while stack:
            element, path = stack.pop()
            ordinal += 1
            self.paths[id(element)] = (path, ordinal)
            counts: dict[str, int] = {}
            children = []
            for child in element:
                if not isinstance(child.tag, str):
                    continue
                counts[child.tag] = counts.get(child.tag, 0) + 1
                children.append((child, f"{path}/{_display(child.tag)}[{counts[child.tag]}]"))
            # Pila invertida para que el ordinal siga el orden del documento.
            stack.extend(reversed(children))

    def lineage(self, element: ET.Element) -> dict[str, Any]:
        path, ordinal = self.paths[id(element)]
        result: dict[str, Any] = {"locator_kind": "xml_element", "path": path,
                                  "element_ordinal": ordinal}
        if self.container:
            result["container"] = self.container
        return result


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()[:MAX_TEXT_LENGTH]


def _find(element: ET.Element, path: str) -> ET.Element | None:
    return element.find(path, NS)


# --------------------------------------------------------------------------- #
# Lectura de la factura
# --------------------------------------------------------------------------- #

def parse_dian_invoice(payload: bytes) -> DianInvoice:
    """Lee un `Invoice` o un `AttachedDocument` DIAN y devuelve campos con linaje.

    Lanza `DianInvoiceError` si el documento es inseguro, esta malformado o no es
    una factura UBL. Un documento legible con huecos devuelve `partial`.
    """
    root = parse_bounded(payload)
    if root.tag == INVOICE_ROOT:
        return _read_invoice(root, _Index(root, ""), "Invoice")
    if root.tag == ATTACHED_ROOT:
        return _read_attached(root)
    uri, name = _local(root.tag)
    if uri.startswith("urn:oasis:names:specification:ubl:schema:xsd:") \
            and name in OTHER_UBL_ROOTS:
        raise DianInvoiceError("unsupported_ubl_document",
                               f"UBL {name} documents are not read as invoices")
    raise DianInvoiceError("not_a_dian_invoice",
                           "the root element is not a UBL 2.1 Invoice or AttachedDocument")


def identify_xml(payload: bytes) -> str:
    """`dian_invoice` si la raiz es UBL Invoice/AttachedDocument; si no, `xml`.

    Solo mira la raiz con el parser acotado: no decide promocion por si mismo.
    """
    root = parse_bounded(payload)
    return "dian_invoice" if root.tag in {INVOICE_ROOT, ATTACHED_ROOT} else "xml"


def _read_attached(root: ET.Element) -> DianInvoice:
    outer = _Index(root, "")
    holder = _find(root, "cac:Attachment/cac:ExternalReference/cbc:Description")
    if holder is None or not (holder.text or "").strip():
        raise DianInvoiceError("attached_document_without_invoice",
                               "the AttachedDocument carries no embedded document")
    container = outer.lineage(holder)["path"]
    # La factura embebida es otro documento no confiable: pasa por los mismos
    # controles, incluido el rechazo de DTD, aunque viniera dentro de un CDATA.
    inner_payload = holder.text.strip().encode("utf-8")
    inner = parse_bounded(inner_payload)
    if inner.tag != INVOICE_ROOT:
        raise DianInvoiceError("attached_document_without_invoice",
                               "the embedded document is not a UBL Invoice")
    return _read_invoice(inner, _Index(inner, container), "AttachedDocument")


def _read_invoice(root: ET.Element, index: _Index, kind: str) -> DianInvoice:
    fields: dict[str, FieldValue] = {}
    findings: list[Finding] = []

    def put_text(name: str, element: ET.Element | None) -> None:
        value = _text(element)
        if element is not None and value:
            fields[name] = FieldValue(name, value, index.lineage(element))

    def put_date(name: str, element: ET.Element | None) -> None:
        value = _text(element)
        if element is None or not value:
            return
        if not _valid_date(value):
            findings.append(Finding("malformed_date", index.lineage(element)["path"],
                                    "the date is not a valid YYYY-MM-DD value"))
            return
        fields[name] = FieldValue(name, value, index.lineage(element))

    put_text("invoice_number", _find(root, "cbc:ID"))
    put_text("cufe", _find(root, "cbc:UUID"))
    put_date("issue_date", _find(root, "cbc:IssueDate"))
    due = _find(root, "cbc:DueDate")
    if due is None:
        due = _find(root, "cac:PaymentMeans/cbc:PaymentDueDate")
    put_date("due_date", due)

    currency = _find(root, "cbc:DocumentCurrencyCode")
    if currency is not None and _text(currency):
        if CURRENCY_CODE.match(_text(currency)):
            fields["currency"] = FieldValue("currency", _text(currency),
                                            index.lineage(currency))
        else:
            findings.append(Finding("malformed_currency", index.lineage(currency)["path"],
                                    "the currency is not an ISO 4217 code"))

    for role, party_path in (("supplier", "cac:AccountingSupplierParty/cac:Party"),
                             ("customer", "cac:AccountingCustomerParty/cac:Party")):
        party = _find(root, party_path)
        if party is None:
            continue
        nit = _find(party, "cac:PartyTaxScheme/cbc:CompanyID")
        if nit is None:
            nit = _find(party, "cac:PartyLegalEntity/cbc:CompanyID")
        put_text(f"{role}_nit", nit)
        if nit is not None and nit.get("schemeID") and f"{role}_nit" in fields:
            # El digito de verificacion viaja como atributo; se conserva aparte
            # para no fabricar un NIT concatenado que el documento no escribio.
            fields[f"{role}_nit_dv"] = FieldValue(
                f"{role}_nit_dv", nit.get("schemeID", "").strip()[:4],
                {**index.lineage(nit), "attribute": "schemeID"})
        name = _find(party, "cac:PartyTaxScheme/cbc:RegistrationName")
        if name is None or not _text(name):
            name = _find(party, "cac:PartyLegalEntity/cbc:RegistrationName")
        if name is None or not _text(name):
            name = _find(party, "cac:PartyName/cbc:Name")
        put_text(f"{role}_name", name)

    document_currency = fields["currency"].value if "currency" in fields else ""
    totals = _find(root, "cac:LegalMonetaryTotal")
    if totals is not None:
        for name, tag in MONETARY_FIELDS.items():
            element = _find(totals, f"cbc:{tag}")
            if element is None:
                continue
            amount = _amount(element, index, document_currency, findings)
            if amount is not None:
                fields[name] = FieldValue(name, amount, index.lineage(element))

    taxes: list[TaxLine] = []
    for kind_name, tag in (("tax", "cac:TaxTotal"), ("withholding", "cac:WithholdingTaxTotal")):
        for total in root.findall(tag, NS):
            amount_element = _find(total, "cbc:TaxAmount")
            if amount_element is None:
                findings.append(Finding("missing_tax_amount", index.lineage(total)["path"],
                                        "a tax total without an amount is not read"))
                continue
            amount = _amount(amount_element, index, document_currency, findings)
            if amount is None:
                continue
            scheme = _find(total, "cac:TaxSubtotal/cac:TaxCategory/cac:TaxScheme")
            taxes.append(TaxLine(
                kind_name,
                _text(_find(scheme, "cbc:ID")) if scheme is not None else "",
                _text(_find(scheme, "cbc:Name")) if scheme is not None else "",
                amount, index.lineage(amount_element)))

    means: list[PaymentMeans] = []
    for element in root.findall("cac:PaymentMeans", NS):
        due_value = _text(_find(element, "cbc:PaymentDueDate"))
        means.append(PaymentMeans(
            _text(_find(element, "cbc:ID")),
            _text(_find(element, "cbc:PaymentMeansCode")),
            tuple(_text(item) for item in element.findall("cbc:PaymentID", NS)
                  if _text(item)),
            due_value if _valid_date(due_value) else "",
            index.lineage(element)))

    missing = tuple(name for name in REQUIRED_FIELDS if name not in fields)
    # Cualquier hallazgo deja el resultado parcial: un importe ilegible o una
    # moneda mezclada no se compensan con el resto de campos bien leidos.
    status = "complete" if not missing and not findings else "partial"
    return DianInvoice(status, kind, fields, tuple(taxes), tuple(means), missing,
                       tuple(findings))


def _valid_date(value: str) -> bool:
    match = STRICT_DATE.match(value)
    if not match:
        return False
    year, month, day = (int(part) for part in match.groups())
    if not (1900 <= year <= 2999 and 1 <= month <= 12):
        return False
    limit = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)[month - 1]
    if month == 2 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        limit = 28
    return 1 <= day <= limit


def _amount(element: ET.Element, index: _Index, document_currency: str,
            findings: list[Finding]) -> Decimal | None:
    """Importe UBL estricto: punto decimal, sin miles, sin exponente."""
    path = index.lineage(element)["path"]
    raw = _text(element)
    if not STRICT_AMOUNT.match(raw):
        findings.append(Finding("malformed_amount", path,
                                "the amount is not a plain decimal with a dot separator"))
        return None
    try:
        amount = parse_money(raw, path)
    except MoneyError:
        findings.append(Finding("malformed_amount", path,
                                "the amount cannot be represented exactly"))
        return None
    declared = (element.get("currencyID") or "").strip()
    if declared and document_currency and declared != document_currency:
        # Mezclar monedas sin tasa produce un numero sin significado.
        findings.append(Finding("currency_mismatch", path,
                                "the amount currency differs from the document currency"))
        return None
    return amount
