"""Contrato del lector de facturas DIAN UBL 2.1 (ADR-039 §5).

Los documentos son sinteticos y se construyen en memoria (`structured_factory`).
Las pruebas negativas usan construcciones hostiles inocuas: una DTD que nunca se
llega a resolver, un documento demasiado grande o profundo, importes con forma
rara. Ninguna depende de red.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

from fincilia_contracts import dian_invoice
from fincilia_contracts.dian_invoice import (DianInvoiceError, identify_xml,
                                             looks_like_xml, parse_bounded,
                                             parse_dian_invoice)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import structured_factory as factory  # noqa: E402


class InvoiceReadingTests(unittest.TestCase):
    def test_a_complete_invoice_reads_every_declared_field(self) -> None:
        result = parse_dian_invoice(factory.invoice())
        self.assertEqual("complete", result.status)
        self.assertEqual("Invoice", result.document_kind)
        self.assertEqual("SYN-FE-0001", result.value("invoice_number"))
        self.assertEqual(factory.CUFE, result.value("cufe"))
        self.assertEqual("2026-03-02", result.value("issue_date"))
        self.assertEqual("2026-04-01", result.value("due_date"))
        self.assertEqual("COP", result.value("currency"))
        self.assertEqual(factory.SUPPLIER_NIT, result.value("supplier_nit"))
        self.assertEqual("9", result.value("supplier_nit_dv"))
        self.assertEqual(factory.SUPPLIER, result.value("supplier_name"))
        self.assertEqual(factory.CUSTOMER_NIT, result.value("customer_nit"))
        self.assertEqual(factory.CUSTOMER, result.value("customer_name"))
        self.assertEqual((), result.missing)

    def test_money_is_exact_decimal(self) -> None:
        result = parse_dian_invoice(factory.invoice())
        for name, expected in (("line_extension_amount", "100000"),
                               ("tax_exclusive_amount", "100000"),
                               ("tax_inclusive_amount", "119000"),
                               ("payable_amount", "119000")):
            value = result.value(name)
            self.assertIsInstance(value, Decimal)
            self.assertEqual(Decimal(expected), value)

    def test_taxes_and_withholdings_are_separated_by_scheme(self) -> None:
        result = parse_dian_invoice(factory.invoice())
        summary = [(item.kind, item.scheme_id, item.scheme_name, item.amount)
                   for item in result.taxes]
        self.assertEqual([("tax", "01", "IVA", Decimal("19000")),
                          ("withholding", "06", "ReteRenta", Decimal("2500"))],
                         [(k, i, n, Decimal(a)) for k, i, n, a in summary])

    def test_payment_means_keep_their_identifiers(self) -> None:
        result = parse_dian_invoice(factory.invoice())
        self.assertEqual(1, len(result.payment_means))
        means = result.payment_means[0]
        self.assertEqual(("2", "42", ("SYN-PAGO-0001",), "2026-04-01"),
                         (means.means_id, means.means_code, means.payment_ids,
                          means.due_date))

    def test_every_field_carries_tag_path_lineage(self) -> None:
        result = parse_dian_invoice(factory.invoice())
        lineage = result.fields["payable_amount"].lineage
        self.assertEqual("xml_element", lineage["locator_kind"])
        self.assertEqual("/Invoice/cac:LegalMonetaryTotal[1]/cbc:PayableAmount[1]",
                         lineage["path"])
        self.assertIsInstance(lineage["element_ordinal"], int)
        nit = result.fields["supplier_nit"].lineage["path"]
        self.assertIn("cac:AccountingSupplierParty[1]", nit)

    def test_the_attached_document_wrapper_is_unwrapped(self) -> None:
        result = parse_dian_invoice(factory.attached_document(factory.invoice_xml()))
        self.assertEqual("AttachedDocument", result.document_kind)
        self.assertEqual("complete", result.status)
        self.assertEqual("SYN-FE-0001", result.value("invoice_number"))
        lineage = result.fields["cufe"].lineage
        self.assertEqual("/AttachedDocument/cac:Attachment[1]/cac:ExternalReference[1]"
                         "/cbc:Description[1]", lineage["container"])
        self.assertEqual("/Invoice/cbc:UUID[1]", lineage["path"])

    def test_a_missing_required_field_is_partial_not_guessed(self) -> None:
        result = parse_dian_invoice(factory.invoice(include_cufe=False))
        self.assertEqual("partial", result.status)
        self.assertEqual(("cufe",), result.missing)

    def test_the_due_date_is_optional(self) -> None:
        result = parse_dian_invoice(factory.invoice(include_due=False))
        # Sigue la fecha de vencimiento del medio de pago, si existe.
        self.assertEqual("2026-04-01", result.value("due_date"))
        self.assertEqual("complete", result.status)

    def test_a_malformed_amount_is_left_out_and_explained(self) -> None:
        for raw in ("119.000,00", "1.19e5", "119000.0000000000001", "", "NaN"):
            with self.subTest(raw=raw):
                result = parse_dian_invoice(factory.invoice(payable=raw))
                self.assertEqual("partial", result.status)
                self.assertIsNone(result.value("payable_amount"))
                self.assertIn("payable_amount", result.missing)

    def test_an_amount_in_another_currency_is_not_mixed(self) -> None:
        result = parse_dian_invoice(factory.invoice(amount_currency="USD"))
        self.assertEqual("partial", result.status)
        self.assertIn("currency_mismatch", {item.code for item in result.findings})
        self.assertIsNone(result.value("payable_amount"))

    def test_the_manifest_carries_no_values(self) -> None:
        manifest = str(parse_dian_invoice(factory.invoice()).manifest())
        for value in (factory.SUPPLIER_NIT, factory.CUFE, "119000", "SYN-FE-0001"):
            self.assertNotIn(value, manifest)

    def test_serialisation_renders_money_as_fixed_point_strings(self) -> None:
        rendered = parse_dian_invoice(factory.invoice()).as_dict()
        self.assertEqual("119000.000000000000",
                         rendered["fields"]["payable_amount"]["value"])


class HostileXmlTests(unittest.TestCase):
    def test_a_doctype_is_rejected_before_parsing(self) -> None:
        hostile = ('<?xml version="1.0"?><!DOCTYPE Invoice [<!ENTITY x SYSTEM '
                   '"file:///etc/hostname">]><Invoice>&x;</Invoice>').encode()
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(hostile)
        self.assertEqual("unsafe_xml_declaration", caught.exception.code)

    def test_entity_expansion_is_rejected(self) -> None:
        laughs = ('<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa">'
                  '<!ENTITY b "&a;&a;&a;&a;">]><l>&b;</l>').encode()
        with self.assertRaises(DianInvoiceError):
            parse_dian_invoice(laughs)

    def test_a_doctype_in_utf16_is_still_seen(self) -> None:
        hostile = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE a []><a/>'
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(hostile.encode("utf-16"))
        self.assertEqual("unsafe_xml_declaration", caught.exception.code)

    def test_a_doctype_hidden_in_the_embedded_invoice_is_rejected(self) -> None:
        inner = factory.invoice_xml(declaration=False)
        escaped = inner.replace("<", "&lt;").replace(">", "&gt;")
        payload = factory.attached_document("").replace(
            b"<![CDATA[]]>", ("&lt;!DOCTYPE Invoice []&gt;" + escaped).encode())
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(payload)
        self.assertEqual("unsafe_xml_declaration", caught.exception.code)

    def test_an_oversized_document_is_refused(self) -> None:
        payload = factory.invoice(extra_inside="<cbc:Note>" + "x" * 2048 + "</cbc:Note>")
        with self.assertRaises(DianInvoiceError) as caught:
            parse_bounded(payload, max_bytes=1024)
        self.assertEqual("xml_too_large", caught.exception.code)
        big = b" " * (dian_invoice.MAX_XML_BYTES + 1)
        with self.assertRaises(DianInvoiceError):
            parse_dian_invoice(big)

    def test_excessive_depth_is_refused_while_reading(self) -> None:
        deep = ("<a>" * (dian_invoice.MAX_XML_DEPTH + 5)
                + "</a>" * (dian_invoice.MAX_XML_DEPTH + 5)).encode()
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(deep)
        self.assertEqual("xml_too_deep", caught.exception.code)

    def test_too_many_elements_are_refused(self) -> None:
        wide = ("<a>" + "<b/>" * 50 + "</a>").encode()
        with self.assertRaises(DianInvoiceError) as caught:
            parse_bounded(wide, max_elements=10)
        self.assertEqual("too_many_elements", caught.exception.code)

    def test_malformed_xml_is_refused(self) -> None:
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(b"<Invoice><cbc:ID>sin cierre")
        self.assertEqual("malformed_xml", caught.exception.code)

    def test_a_foreign_root_is_not_an_invoice(self) -> None:
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(b"<Invoice><ID>1</ID></Invoice>")
        # Sin el espacio de nombres UBL, el nombre de la raiz no basta.
        self.assertEqual("not_a_dian_invoice", caught.exception.code)

    def test_a_credit_note_is_named_as_unsupported(self) -> None:
        note = (b'<CreditNote xmlns="urn:oasis:names:specification:ubl:schema:xsd:'
                b'CreditNote-2"/>')
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(note)
        self.assertEqual("unsupported_ubl_document", caught.exception.code)

    def test_an_attached_document_without_invoice_is_refused(self) -> None:
        with self.assertRaises(DianInvoiceError) as caught:
            parse_dian_invoice(factory.attached_document("<Otro/>"))
        self.assertEqual("attached_document_without_invoice", caught.exception.code)


class SniffingTests(unittest.TestCase):
    def test_xml_is_recognised_by_its_first_bytes(self) -> None:
        self.assertTrue(looks_like_xml(factory.invoice()))
        self.assertTrue(looks_like_xml(b"\xef\xbb\xbf  <Invoice xmlns='x'/>"))
        self.assertFalse(looks_like_xml(b"fecha,valor\n"))
        self.assertFalse(looks_like_xml(b"<<no>>"))

    def test_identify_tells_invoice_from_generic_xml(self) -> None:
        self.assertEqual("dian_invoice", identify_xml(factory.invoice()))
        self.assertEqual("xml", identify_xml(b"<nota>FNC-SYN</nota>"))


if __name__ == "__main__":
    unittest.main()
