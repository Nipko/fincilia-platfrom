"""Fabrica de documentos estructurados 100 % sinteticos, en memoria.

Origen: plantilla propia escrita desde cero a partir de la estructura publica de
UBL 2.1 (OASIS) y del formato SWIFT MT940. Ningun valor proviene de un documento
real: nombres con prefijo `FNC-SYN`, NIT como tokens `FNC-SYN-NIT-*` y cuentas y
referencias con prefijo `SYN`, segun docs/testing/SYNTHETIC_DATA_POLICY.md §5.
Nada se escribe a disco ni se consulta fuera de la prueba.
"""

from __future__ import annotations

UBL_NAMESPACES = (
    'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
    'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"')

SUPPLIER = "FNC-SYN Comercio Sintetico Andino S.A.S."
CUSTOMER = "FNC-SYN Cliente Cascada 001"
SUPPLIER_NIT = "FNC-SYN-NIT-0001"
CUSTOMER_NIT = "FNC-SYN-NIT-0002"
CUFE = "FNC-SYN-CUFE-0001"


def _party(role: str, nit: str, name: str) -> str:
    return (f"<cac:{role}><cac:Party>"
            f"<cac:PartyName><cbc:Name>{name}</cbc:Name></cac:PartyName>"
            f"<cac:PartyTaxScheme><cbc:RegistrationName>{name}</cbc:RegistrationName>"
            f'<cbc:CompanyID schemeAgencyID="195" schemeID="9" schemeName="31">{nit}'
            f"</cbc:CompanyID></cac:PartyTaxScheme></cac:Party></cac:{role}>")


def invoice_xml(*, number: str = "SYN-FE-0001", payable: str = "119000.00",
                currency: str = "COP", amount_currency: str = "COP",
                include_cufe: bool = True, include_due: bool = True,
                withholding: bool = True, declaration: bool = True,
                extra_inside: str = "") -> str:
    def money(tag: str, value: str) -> str:
        return f'<cbc:{tag} currencyID="{amount_currency}">{value}</cbc:{tag}>'

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>' if declaration else "",
        f'<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
        f"{UBL_NAMESPACES}>",
        extra_inside,
        "<cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>",
        f"<cbc:ID>{number}</cbc:ID>",
        f'<cbc:UUID schemeName="CUFE-SHA384">{CUFE}</cbc:UUID>' if include_cufe else "",
        "<cbc:IssueDate>2026-03-02</cbc:IssueDate>",
        "<cbc:DueDate>2026-04-01</cbc:DueDate>" if include_due else "",
        f"<cbc:DocumentCurrencyCode>{currency}</cbc:DocumentCurrencyCode>",
        _party("AccountingSupplierParty", SUPPLIER_NIT, SUPPLIER),
        _party("AccountingCustomerParty", CUSTOMER_NIT, CUSTOMER),
        "<cac:PaymentMeans><cbc:ID>2</cbc:ID><cbc:PaymentMeansCode>42</cbc:PaymentMeansCode>"
        "<cbc:PaymentDueDate>2026-04-01</cbc:PaymentDueDate>"
        "<cbc:PaymentID>SYN-PAGO-0001</cbc:PaymentID></cac:PaymentMeans>",
        "<cac:TaxTotal>", money("TaxAmount", "19000.00"),
        "<cac:TaxSubtotal>", money("TaxableAmount", "100000.00"),
        money("TaxAmount", "19000.00"),
        "<cac:TaxCategory><cbc:Percent>19.00</cbc:Percent><cac:TaxScheme>"
        "<cbc:ID>01</cbc:ID><cbc:Name>IVA</cbc:Name></cac:TaxScheme></cac:TaxCategory>",
        "</cac:TaxSubtotal></cac:TaxTotal>",
    ]
    if withholding:
        parts += [
            "<cac:WithholdingTaxTotal>", money("TaxAmount", "2500.00"),
            "<cac:TaxSubtotal>", money("TaxableAmount", "100000.00"),
            money("TaxAmount", "2500.00"),
            "<cac:TaxCategory><cbc:Percent>2.50</cbc:Percent><cac:TaxScheme>"
            "<cbc:ID>06</cbc:ID><cbc:Name>ReteRenta</cbc:Name></cac:TaxScheme>"
            "</cac:TaxCategory></cac:TaxSubtotal></cac:WithholdingTaxTotal>",
        ]
    parts += [
        "<cac:LegalMonetaryTotal>",
        money("LineExtensionAmount", "100000.00"),
        money("TaxExclusiveAmount", "100000.00"),
        money("TaxInclusiveAmount", "119000.00"),
        money("PayableAmount", payable),
        "</cac:LegalMonetaryTotal>",
        "</Invoice>",
    ]
    return "".join(parts)


def invoice(**kwargs) -> bytes:
    return invoice_xml(**kwargs).encode("utf-8")


def attached_document(inner: str) -> bytes:
    """Envoltorio `AttachedDocument` con la factura en un CDATA, como la DIAN."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:'
        f'AttachedDocument-2" {UBL_NAMESPACES}>'
        "<cbc:UBLVersionID>UBL 2.1</cbc:UBLVersionID>"
        "<cbc:ID>SYN-AD-0001</cbc:ID>"
        "<cac:Attachment><cac:ExternalReference>"
        "<cbc:MimeCode>text/xml</cbc:MimeCode>"
        f"<cbc:Description><![CDATA[{inner}]]></cbc:Description>"
        "</cac:ExternalReference></cac:Attachment>"
        "</AttachedDocument>").encode("utf-8")


def mt940(*, closing: str = "C260331COP1080000,00",
          second_amount: str = "50000,00", envelope: bool = False) -> bytes:
    """Un extracto: 1.000.000 + 150.000 - 50.000 - 20.000 = 1.080.000."""
    lines = [
        ":20:SYN-STMT-0001",
        ":25:SYN-CTA-0001",
        ":28C:00001/001",
        ":60F:C260301COP1000000,00",
        ":61:2603020302C150000,00NTRFSYN-REF-0001//SYN-BNK-0001",
        "FNC-SYN abono cliente",
        ":86:FNC-SYN Cliente Cascada 001",
        "pago factura SYN-FE-0001",
        f":61:260310D{second_amount}NCHGNONREF",
        ":86:FNC-SYN comision bancaria",
        ":61:260315RC20000,00NTRFSYN-REF-0002",
        ":86:FNC-SYN reverso de abono",
        f":62F:{closing}",
        ":64:C260331COP1080000,00",
    ]
    body = "\r\n".join(lines)
    if envelope:
        body = ("{1:F01SYNBANKXAXXX0000000000}{2:I940SYNBANKXXXXXN}{4:\r\n"
                + body + "\r\n-}")
    return (body + "\r\n").encode("ascii")
