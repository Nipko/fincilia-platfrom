"""Contrato de las plantillas por banco (ADR-039 §5).

Las filas son sinteticas (`FNC-SYN`, referencias `SYN`) y solo usan las
cabeceras-hipotesis de cada plantilla; ningun valor imita un extracto real.
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from fincilia_contracts.bank_templates import (CALIBRATION, NO_PUBLIC_SOURCE, TEMPLATES,
                                               BankTemplate, detect_template,
                                               find_header, normalise_header,
                                               propose_mapping)
from fincilia_contracts.extraction import extract
from fincilia_contracts.mapping import CANONICAL_FIELDS, apply, validate_mapping


def template(template_id: str) -> BankTemplate:
    return next(item for item in TEMPLATES if item.template_id == template_id)


def headers_of(item: BankTemplate) -> list[str]:
    return [aliases[0].upper() for aliases in item.columns.values()]


BANCOLOMBIA_HEADERS = ["FECHA", "DESCRIPCIÓN", "SUCURSAL", "DCTO.", "VALOR", "SALDO"]
BANCOLOMBIA_ROWS = [
    ["02/03/2026", "FNC-SYN abono cliente", "SYN-OF-01", "SYN-0001", "1.250.000,50",
     "3.250.000,50"],
    ["05/03/2026", "FNC-SYN pago proveedor", "SYN-OF-01", "SYN-0002", "-200.000,00",
     "3.050.000,50"],
]


class CatalogueTests(unittest.TestCase):
    def test_every_template_is_a_declared_synthetic_hypothesis(self) -> None:
        self.assertEqual(5, len(TEMPLATES))
        for item in TEMPLATES:
            with self.subTest(template=item.template_id):
                self.assertEqual(CALIBRATION, item.calibration)
                self.assertEqual("synthetic_hypothesis", item.calibration)
                self.assertTrue(item.source_url == NO_PUBLIC_SOURCE
                                or item.source_url.startswith("https://"))
                self.assertTrue(item.source_note)

    def test_every_template_maps_into_canonical_or_declared_extra_fields(self) -> None:
        for item in TEMPLATES:
            with self.subTest(template=item.template_id):
                for alias_list in item.columns.values():
                    for alias in alias_list:
                        self.assertEqual(alias, normalise_header(alias))
                self.assertTrue(set(item.required) <= set(item.columns))
                self.assertIn("occurred_on", item.required)
                self.assertIn("description", item.required)

    def test_each_template_detects_only_itself(self) -> None:
        for item in TEMPLATES:
            with self.subTest(template=item.template_id):
                match = detect_template(headers_of(item))
                self.assertIsNotNone(match)
                self.assertEqual(item.template_id, match.template.template_id)


class DetectionTests(unittest.TestCase):
    def test_headers_are_normalised_without_accents_case_or_padding(self) -> None:
        self.assertEqual("descripcion", normalise_header("  DESCRIPCIÓN "))
        self.assertEqual("dcto", normalise_header("Dcto."))
        self.assertEqual("fecha valor", normalise_header("Fecha   Valor"))

    def test_a_known_export_is_detected(self) -> None:
        match = detect_template(BANCOLOMBIA_HEADERS)
        self.assertEqual("bancolombia-cuenta-movimientos", match.template.template_id)
        self.assertEqual({"occurred_on": 0, "description": 1, "branch": 2,
                          "reference": 3, "amount": 4, "balance": 5}, match.columns)

    def test_a_missing_required_header_falls_back_to_manual(self) -> None:
        self.assertIsNone(detect_template(["FECHA", "DESCRIPCION", "VALOR"]))

    def test_an_unknown_extra_header_falls_back_to_manual(self) -> None:
        self.assertIsNone(detect_template(BANCOLOMBIA_HEADERS + ["CANAL"]))

    def test_a_repeated_header_falls_back_to_manual(self) -> None:
        self.assertIsNone(detect_template(BANCOLOMBIA_HEADERS + ["VALOR"]))

    def test_two_matching_templates_are_ambiguous(self) -> None:
        base = template("bancolombia-cuenta-movimientos")
        twin = BankTemplate(**{**base.__dict__, "template_id": "fnc-syn-gemela",
                               "bank": "FNC-SYN Banco"})
        self.assertIsNone(detect_template(BANCOLOMBIA_HEADERS, templates=(base, twin)))
        self.assertIsNotNone(detect_template(BANCOLOMBIA_HEADERS, templates=(base,)))

    def test_the_header_is_found_after_a_preamble(self) -> None:
        rows = [["FNC-SYN Banco - movimientos"], ["Cuenta", "SYN-CTA-0001"], [],
                BANCOLOMBIA_HEADERS, *BANCOLOMBIA_ROWS]
        match = find_header(rows)
        self.assertEqual(4, match.header_row)

    def test_two_header_candidates_are_ambiguous(self) -> None:
        rows = [BANCOLOMBIA_HEADERS, *BANCOLOMBIA_ROWS, BANCOLOMBIA_HEADERS]
        self.assertIsNone(find_header(rows))


class ProposalTests(unittest.TestCase):
    def test_a_csv_export_gets_a_ready_mapping_with_no_manual_step(self) -> None:
        lines = [";".join(BANCOLOMBIA_HEADERS)] + [";".join(row) for row in BANCOLOMBIA_ROWS]
        payload = ("\n".join(lines) + "\n").encode("utf-8")
        extraction = extract(payload)
        match = find_header([extraction.header, *extraction.data_rows()])
        proposal = propose_mapping(match, extraction.data_rows())
        self.assertEqual("ready", proposal.status)
        self.assertEqual([], validate_mapping(proposal.mapping))
        self.assertEqual(("dmy", "comma", "signed_amount", "COP"),
                         (proposal.mapping.date_format, proposal.mapping.decimal_format,
                          proposal.mapping.direction_mode, proposal.mapping.currency))
        self.assertTrue(set(proposal.definition["columns"]) <= set(CANONICAL_FIELDS))
        self.assertEqual({"branch": 2, "balance": 5}, proposal.extra_columns)
        self.assertEqual([2, 5], proposal.definition["ignored_columns"])
        self.assertEqual("synthetic_hypothesis",
                         proposal.definition["template"]["calibration"])
        result = apply(proposal.mapping, [list(row.values)
                                          for row in extraction.data_rows()])
        self.assertEqual([(Decimal("1250000.50"), "inflow"),
                          (Decimal("200000.00"), "outflow")],
                         [(item.amount, item.direction) for item in result.movements])

    def test_xlsx_style_values_select_iso_and_dot(self) -> None:
        match = detect_template(BANCOLOMBIA_HEADERS)
        rows = [["2026-03-02", "FNC-SYN abono", "SYN-OF-01", "SYN-1", "1250000.5", "1"]]
        proposal = propose_mapping(match, rows)
        self.assertEqual("ready", proposal.status)
        self.assertEqual(("iso", "dot"), (proposal.mapping.date_format,
                                          proposal.mapping.decimal_format))

    def test_debit_credit_and_explicit_direction_templates_propose(self) -> None:
        bogota = detect_template(["Fecha", "Transacción", "Oficina", "Documento",
                                  "Débitos", "Créditos", "Saldo"])
        proposal = propose_mapping(bogota, [
            ["02/03/2026", "FNC-SYN abono", "SYN-OF", "SYN-1", "", "10.000,00", "1"],
            ["03/03/2026", "FNC-SYN cargo", "SYN-OF", "SYN-2", "2.500,00", "", "1"]])
        self.assertEqual("ready", proposal.status)
        self.assertEqual("debit_credit_columns", proposal.mapping.direction_mode)

        nequi = detect_template(["Fecha del movimiento", "Detalle", "Tipo de movimiento",
                                 "Valor", "Saldo disponible"])
        proposal = propose_mapping(nequi, [
            ["02/03/2026", "FNC-SYN venta", "Entrada", "35.000,00", "1"],
            ["02/03/2026", "FNC-SYN compra", "Salida", "5.000,00", "1"]])
        self.assertEqual("ready", proposal.status)
        self.assertEqual("explicit_direction", proposal.mapping.direction_mode)

    def test_two_locale_readings_with_different_amounts_need_review(self) -> None:
        match = detect_template(BANCOLOMBIA_HEADERS)
        # `1.234` es mil doscientos treinta y cuatro o uno coma doscientos...
        rows = [["2026-03-02", "FNC-SYN", "SYN-OF", "SYN-1", "1.234", "1"]]
        proposal = propose_mapping(match, rows)
        self.assertEqual("needs_review", proposal.status)
        self.assertIsNone(proposal.mapping)
        self.assertIn("ambiguous_locale", proposal.findings)

    def test_a_row_that_does_not_map_needs_review(self) -> None:
        match = detect_template(BANCOLOMBIA_HEADERS)
        rows = [*BANCOLOMBIA_ROWS, ["Total", "", "", "", "", ""]]
        proposal = propose_mapping(match, rows)
        self.assertEqual("needs_review", proposal.status)
        self.assertIsNone(proposal.definition)

    def test_no_data_rows_needs_review(self) -> None:
        match = detect_template(BANCOLOMBIA_HEADERS)
        self.assertEqual("needs_review", propose_mapping(match, [[""] * 6]).status)


if __name__ == "__main__":
    unittest.main()
