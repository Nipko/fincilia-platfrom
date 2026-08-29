"""Contrato de admision de ficheros.

Cada prueba describe una forma concreta de meter en el sistema algo que no
deberia entrar, o de que algo legitimo se quede fuera. Se trabaja con bytes
exactos, que es lo unico que hay al otro lado de una subida.
"""

from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Cadenas con forma de credencial, compuestas en ejecucion. La politica del
# repositorio prohibe dejarlas literales, y hace bien: una excepcion por fichero
# podria tapar manana una clave de verdad. Ninguna de estas identifica nada.
AWS_SHAPED = "AKIA" + "IOSFODNN7EXAMPLE"
PRIVATE_KEY_HEADER = "-----BEGIN RSA " + "PRIVATE KEY-----"

from fincilia_contracts.ingestion import (ACCEPTED_MEDIA_TYPES, FULLY_INSPECTABLE,
                                          MAX_ARCHIVE_ENTRIES, MAX_COMPRESSION_RATIO,
                                          MAX_UPLOAD_BYTES, Admission, RejectedUpload,
                                          admit, count_lines, decide_promotion, detect,
                                          extension_type, identify_archive,
                                          inspect_archive, luhn_valid, scan_secrets,
                                          sha256_bytes)
from xlsx_factory import build_xlsx
from ods_factory import build_ods

CSV = b"fecha,descripcion,valor\n2026-01-02,Pago proveedor,-125000.00\n"
NEWLINE = b"\n"
PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n"


def build_zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in entries.items():
            archive.writestr(name, body)
    return buffer.getvalue()


class DetectionTests(unittest.TestCase):
    def test_a_csv_is_detected_by_its_delimiters(self) -> None:
        self.assertEqual("text/csv", detect(CSV, "extracto.csv").media_type)

    def test_a_pdf_is_detected_by_its_signature(self) -> None:
        self.assertEqual("application/pdf", detect(PDF, "factura.pdf").media_type)

    def test_the_signature_wins_over_the_extension(self) -> None:
        # El caso que justifica el modulo entero: el nombre dice CSV, los bytes
        # dicen PDF. Se cree a los bytes.
        detection = detect(PDF, "extracto.csv")
        self.assertEqual("application/pdf", detection.media_type)
        self.assertFalse(detection.extension_matches)

    def test_a_renamed_executable_is_refused(self) -> None:
        for payload, label in ((b"MZ\x90\x00" + b"\x00" * 64, "windows"),
                               (b"\x7fELF\x02\x01\x01" + b"\x00" * 64, "linux"),
                               (b"#!/bin/sh\nrm -rf /\n", "script")):
            with self.subTest(label=label):
                with self.assertRaises(RejectedUpload):
                    detect(payload, "extracto.csv")

    def test_an_unknown_binary_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            detect(bytes(range(256)) * 8, "cosa.csv")

    def test_an_image_is_detected_and_then_not_accepted(self) -> None:
        # Se detecta bien; simplemente no esta en la lista de tipos admitidos.
        detection = detect(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "captura.png")
        self.assertEqual("image/png", detection.media_type)
        self.assertFalse(detection.accepted)

    def test_plain_text_without_delimiters_is_not_a_csv(self) -> None:
        self.assertEqual("text/plain", detect(b"solo una nota\n", "nota.txt").media_type)

    def test_the_extension_map_and_the_accepted_types_agree(self) -> None:
        for media_type in ACCEPTED_MEDIA_TYPES:
            self.assertIn(media_type, set(extension_type(f"x{ext}") or ""
                                          for ext in (".csv", ".pdf", ".xlsx")) |
                          ACCEPTED_MEDIA_TYPES)


class SizeTests(unittest.TestCase):
    def test_an_empty_file_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"", "vacio.csv")

    def test_a_file_over_the_ceiling_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"a,b\n" * (MAX_UPLOAD_BYTES // 4 + 1), "enorme.csv")

    def test_the_line_ceiling_is_enforced(self) -> None:
        with self.assertRaises(RejectedUpload):
            count_lines(b"\n" * 1_000_001)


class ArchiveTests(unittest.TestCase):
    def test_a_normal_spreadsheet_archive_passes(self) -> None:
        payload = build_zip({"xl/worksheets/sheet1.xml": b"<sheet/>" * 100})
        self.assertEqual([], inspect_archive(payload))

    def test_a_zip_bomb_is_refused_without_expanding_it(self) -> None:
        # Un mega de ceros comprime a casi nada: la cabecera ya lo delata.
        payload = build_zip({"grande.csv": b"0" * (2 * 1024 * 1024)})
        self.assertLess(len(payload), 64 * 1024)
        with self.assertRaises(RejectedUpload):
            inspect_archive(payload)

    def test_too_many_entries_is_refused(self) -> None:
        payload = build_zip({f"e{index}.csv": b"a,b\n"
                             for index in range(MAX_ARCHIVE_ENTRIES + 1)})
        with self.assertRaises(RejectedUpload):
            inspect_archive(payload)

    def test_a_path_that_escapes_the_root_is_refused(self) -> None:
        for name in ("../fuera.csv", "/etc/passwd", "a/../../b.csv"):
            with self.subTest(name=name):
                with self.assertRaises(RejectedUpload):
                    inspect_archive(build_zip({name: b"a,b\n"}))

    def test_a_broken_archive_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            inspect_archive(b"PK\x03\x04 pero no es un zip")

    def test_the_ratio_ceiling_is_a_real_number(self) -> None:
        self.assertGreater(MAX_COMPRESSION_RATIO, 1)


class LuhnTests(unittest.TestCase):
    def test_a_valid_test_number_passes(self) -> None:
        # Numero de prueba publico de la industria; no corresponde a ninguna
        # tarjeta emitida.
        self.assertTrue(luhn_valid("4111111111111111"))

    def test_one_changed_digit_fails(self) -> None:
        self.assertFalse(luhn_valid("4111111111111112"))

    def test_a_long_account_identifier_is_not_a_card(self) -> None:
        self.assertFalse(luhn_valid("1234567890123"))


class SecretScanTests(unittest.TestCase):
    def test_a_card_number_is_found(self) -> None:
        findings = scan_secrets(b"cliente,tarjeta\nJuan,4111 1111 1111 1111\n")
        self.assertEqual(["payment_card_number"], [item.kind for item in findings])
        self.assertEqual("line 2", findings[0].location)

    def test_a_finding_never_repeats_the_value(self) -> None:
        # Lo mas importante del modulo: contener un secreto no puede consistir en
        # copiarlo a un sitio con menos proteccion.
        payload = f"tarjeta\n4111111111111111\n{AWS_SHAPED}\n".encode("utf-8")
        for finding in scan_secrets(payload):
            rendered = " ".join(finding.as_dict().values())
            self.assertNotIn("4111111111111111", rendered)
            self.assertNotIn(AWS_SHAPED, rendered)

    def test_credentials_are_found_by_shape(self) -> None:
        cases = {
            "private_key": f"{PRIVATE_KEY_HEADER}\n".encode("utf-8"),
            "aws_access_key": f"key,{AWS_SHAPED}\n".encode("utf-8"),
            "bearer_token": b"header: Bearer abcdefghijklmnopqrstuvwxyz012345\n",
            "password_assignment": b"password: sup3rsecreto\n",
            "connection_string": b"dsn,postgresql://usuario:clave@host/db\n",
        }
        for kind, payload in cases.items():
            with self.subTest(kind=kind):
                self.assertIn(kind, [item.kind for item in scan_secrets(payload)])

    def test_an_ordinary_ledger_line_is_not_a_secret(self) -> None:
        # Si esto fallara, el escaner seria ruido y la gente aprenderia a
        # ignorarlo, que es peor que no tenerlo.
        self.assertEqual([], scan_secrets(CSV))

    def test_an_invoice_number_is_not_a_card(self) -> None:
        self.assertEqual([], scan_secrets(b"factura,valor\nFAC-2026-000123,15000\n"))

    def test_the_number_of_findings_is_bounded(self) -> None:
        payload = b"4111111111111111\n" * 500
        self.assertLessEqual(len(scan_secrets(payload)), 50)

    def test_bytes_that_are_not_utf8_do_not_crash_the_scan(self) -> None:
        self.assertEqual([], scan_secrets(b"\xff\xfe descripcion sin sentido\n"))


class AdmissionTests(unittest.TestCase):
    """`admit` decide si unos bytes **entran**, no si pueden salir."""

    def test_everything_that_enters_lands_in_quarantine(self) -> None:
        # La regla que ordena el resto: la subida no promueve nada. El DFD declara
        # la subida como `evidence_quarantine_only` y la promocion como un flujo
        # aparte con su propia decision persistida.
        for payload, name in ((CSV, "extracto.csv"), (PDF, "factura.pdf"),
                              (build_zip({"a.csv": b"x,y" + NEWLINE}), "libro.xlsx")):
            with self.subTest(name=name):
                self.assertEqual("quarantine", admit(payload, name).zone)

    def test_an_empty_file_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"", "vacio.csv")

    def test_a_file_over_the_ceiling_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"a,b" + NEWLINE * (MAX_UPLOAD_BYTES // 4 + 1), "enorme.csv")

    def test_an_unaccepted_type_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "captura.png")

    def test_plain_text_without_structure_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"una nota suelta sin estructura" + NEWLINE, "nota.txt")

    def test_a_zip_bomb_never_even_reaches_quarantine(self) -> None:
        # Los limites del contenedor se comprueban en la puerta: una bomba no se
        # guarda ni siquiera para mirarla luego.
        payload = build_zip({"grande.csv": b"0" * (2 * 1024 * 1024)})
        with self.assertRaises(RejectedUpload):
            admit(payload, "libro.xlsx")

    def test_a_mismatched_extension_is_recorded_but_not_fatal(self) -> None:
        admission = admit(CSV, "extracto.txt")
        self.assertEqual("quarantine", admission.zone)
        self.assertFalse(admission.extension_matches)
        self.assertIn("extension_mismatch", [item.kind for item in admission.findings])

    def test_the_same_bytes_always_give_the_same_digest(self) -> None:
        self.assertEqual(admit(CSV, "a.csv").content_sha256,
                         admit(CSV, "b.csv").content_sha256)

    def test_one_changed_byte_changes_the_digest(self) -> None:
        self.assertNotEqual(
            admit(CSV, "a.csv").content_sha256,
            admit(CSV.replace(b"125000", b"125001"), "a.csv").content_sha256)

    def test_the_report_is_serialisable_and_carries_no_payload(self) -> None:
        self.assertNotIn("Pago proveedor", str(admit(CSV, "extracto.csv").as_dict()))

    def test_an_admission_is_immutable(self) -> None:
        admission = admit(CSV, "extracto.csv")
        with self.assertRaises(Exception):
            admission.zone = "raw"  # type: ignore[misc]
        self.assertIsInstance(admission, Admission)


class ArchiveIdentityTests(unittest.TestCase):
    """Un ZIP es un contenedor, no un tipo."""

    def test_a_spreadsheet_is_identified_by_its_manifest(self) -> None:
        payload = build_zip({"[Content_Types].xml": b"<Types/>",
                             "xl/workbook.xml": b"<workbook/>"})
        self.assertEqual("xlsx", identify_archive(payload))

    def test_an_open_document_sheet_is_identified_by_its_mimetype(self) -> None:
        payload = build_zip({
            "mimetype": b"application/vnd.oasis.opendocument.spreadsheet",
            "content.xml": b"<office/>"})
        self.assertEqual("ods", identify_archive(payload))

    def test_a_plain_zip_is_not_mistaken_for_a_spreadsheet(self) -> None:
        # Renombrar un ZIP a `.xlsx` no lo convierte en una hoja de calculo, y
        # decidirlo por la extension seria dejarlo en manos de quien lo sube.
        self.assertEqual("zip", identify_archive(build_zip({"a.txt": b"hola"})))

    def test_a_macro_enabled_workbook_is_identified(self) -> None:
        payload = build_zip({"[Content_Types].xml": b"<Types/>",
                             "xl/workbook.xml": b"<workbook/>",
                             "xl/vbaProject.bin": b"\x00\x01"})
        self.assertEqual("macro_enabled", identify_archive(payload))


class PromotionTests(unittest.TestCase):
    """`decide_promotion` es la unica puerta hacia la zona de evidencia."""

    def test_a_clean_csv_is_promoted_after_being_read_whole(self) -> None:
        decision = decide_promotion(CSV, "extracto.csv")
        self.assertTrue(decision.promoted)
        self.assertEqual("content_inspected", decision.reason_code)
        self.assertEqual((), decision.findings)

    def test_a_csv_with_a_card_stays_in_quarantine(self) -> None:
        decision = decide_promotion(b"cliente,tarjeta" + NEWLINE +
                                    b"Juan,4111111111111111" + NEWLINE, "clientes.csv")
        self.assertFalse(decision.promoted)
        self.assertEqual("sensitive_content", decision.reason_code)
        self.assertIn("payment_card_number", [item.kind for item in decision.findings])
        # El hallazgo dice donde y de que tipo, nunca el valor.
        self.assertNotIn("4111111111111111", str(decision.as_dict()))

    def test_a_pdf_is_never_promoted_without_being_inspected(self) -> None:
        # El defecto que motivo esta rebanada: un PDF llegaba a la zona de evidencia
        # sin que nadie hubiera mirado su contenido.
        decision = decide_promotion(PDF, "factura.pdf")
        self.assertFalse(decision.promoted)
        self.assertEqual("no_scanner_for_format", decision.reason_code)

    def test_a_clean_single_sheet_workbook_is_promoted_after_full_inspection(self) -> None:
        payload = build_xlsx([
            ["Fecha", "Descripcion", "Importe"],
            ["2026-01-02", "Pago sintetico", -1250],
        ])
        decision = decide_promotion(payload, "libro.xlsx")
        self.assertTrue(decision.promoted)
        self.assertEqual("content_inspected", decision.reason_code)
        self.assertEqual("xlsx", decision.internal_type)

    def test_an_xlsx_secret_is_found_without_copying_its_value(self) -> None:
        pan = "4111" + "1111" + "1111" + "1111"
        payload = build_xlsx([["Cliente", "Tarjeta"], ["Sintetico", pan]])
        decision = decide_promotion(payload, "libro.xlsx")
        self.assertEqual("quarantined", decision.decision)
        self.assertEqual("sensitive_content", decision.reason_code)
        self.assertNotIn(pan, repr(decision.as_dict()))

    def test_a_clean_ods_is_promoted_and_a_secret_is_minimized(self) -> None:
        clean = decide_promotion(build_ods([
            ["Fecha", "Descripcion", "Importe"],
            ["2026-01-02", "Pago sintetico", -1250],
        ]), "libro.ods")
        self.assertTrue(clean.promoted)
        self.assertEqual("ods", clean.internal_type)
        pan = "4111" + "1111" + "1111" + "1111"
        sensitive = decide_promotion(build_ods(
            [["Cliente", "Tarjeta"], ["Sintetico", pan]]), "libro.ods")
        self.assertEqual("sensitive_content", sensitive.reason_code)
        self.assertNotIn(pan, repr(sensitive.as_dict()))

    def test_formula_and_multiple_sheet_books_use_explicit_flows(self) -> None:
        formula = decide_promotion(build_xlsx(
            [["Importe"], [10]], formula_at=(2, 1)), "formula.xlsx")
        self.assertEqual("formula_review_required", formula.reason_code)
        multiple = decide_promotion(build_xlsx(
            [["A"], ["uno"]], second_sheet=[["B"], ["dos"]]), "multi.xlsx")
        self.assertTrue(multiple.promoted)
        self.assertEqual("content_inspected_selection_required", multiple.reason_code)
        self.assertTrue(multiple.requires_selection)
        self.assertEqual(2, multiple.workbook["sheet_count"])
        self.assertNotIn("uno", repr(multiple.as_dict()))
        self.assertNotIn("dos", repr(multiple.as_dict()))

        ods_formula = decide_promotion(
            build_ods([["Importe"], [10]], formula_at=(2, 1)), "formula.ods")
        self.assertEqual("formula_review_required", ods_formula.reason_code)
        ods_multiple = decide_promotion(build_ods(
            [["A"], ["uno"]], second_sheet=[["B"], ["dos"]]), "multi.ods")
        self.assertTrue(ods_multiple.promoted)
        self.assertTrue(ods_multiple.requires_selection)
        self.assertNotIn("uno", repr(ods_multiple.as_dict()))
        self.assertNotIn("dos", repr(ods_multiple.as_dict()))

    def test_active_workbook_content_is_rejected(self) -> None:
        decision = decide_promotion(build_xlsx(
            [["A"], ["uno"]], active_part="xl/embeddings/object1.bin"),
            "activo.xlsx")
        self.assertEqual("rejected", decision.decision)
        self.assertEqual("active_workbook_content", decision.reason_code)

    def test_a_generic_zip_is_never_promoted(self) -> None:
        decision = decide_promotion(build_zip({"a.txt": b"hola"}), "cosas.zip")
        self.assertFalse(decision.promoted)
        self.assertEqual("zip", decision.internal_type)

    def test_a_macro_enabled_workbook_is_rejected_outright(self) -> None:
        payload = build_zip({"[Content_Types].xml": b"<Types/>",
                             "xl/workbook.xml": b"<workbook/>",
                             "xl/vbaProject.bin": b"\x00"})
        decision = decide_promotion(payload, "libro.xlsx")
        self.assertEqual("rejected", decision.decision)
        self.assertEqual("macro_enabled_archive", decision.reason_code)

    def test_only_what_can_be_read_whole_is_promotable(self) -> None:
        # Si esta lista creciera sin un analizador detras, la regla dejaria de
        # significar nada.
        self.assertEqual({"text/csv", "xlsx", "ods"}, set(FULLY_INSPECTABLE))
        self.assertNotIn("application/zip", FULLY_INSPECTABLE)
        self.assertNotIn("application/pdf", FULLY_INSPECTABLE)

    def test_quarantine_keeps_the_file_instead_of_deleting_it(self) -> None:
        # Ningun camino devuelve «borrado»: borrar la evidencia de un incidente
        # es la peor forma de responder a uno.
        decision = decide_promotion(b"campo,valor" + NEWLINE +
                                    b"clave,password: sup3rsecreto" + NEWLINE,
                                    "config.csv")
        self.assertIn(decision.decision, {"quarantined", "rejected", "promoted"})
        self.assertEqual("quarantined", decision.decision)

    def test_a_decision_is_serialisable_without_the_payload(self) -> None:
        rendered = str(decide_promotion(CSV, "extracto.csv").as_dict())
        self.assertNotIn("Pago proveedor", rendered)


if __name__ == "__main__":
    unittest.main()
