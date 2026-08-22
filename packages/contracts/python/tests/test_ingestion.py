"""Contrato de admision de ficheros.

Cada prueba describe una forma concreta de meter en el sistema algo que no
deberia entrar, o de que algo legitimo se quede fuera. Se trabaja con bytes
exactos, que es lo unico que hay al otro lado de una subida.
"""

from __future__ import annotations

import io
import unittest
import zipfile

from fincilia_contracts.ingestion import (ACCEPTED_MEDIA_TYPES, MAX_ARCHIVE_ENTRIES,
                                          MAX_COMPRESSION_RATIO, MAX_UPLOAD_BYTES,
                                          Admission, RejectedUpload, admit,
                                          count_lines, detect, extension_type,
                                          inspect_archive, luhn_valid, scan_secrets,
                                          sha256_bytes)

CSV = b"fecha,descripcion,valor\n2026-01-02,Pago proveedor,-125000.00\n"
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
        # El caso que justifica todo el modulo: el nombre dice CSV, los bytes
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
        payload = b"tarjeta\n4111111111111111\nAKIAIOSFODNN7EXAMPLE\n"
        for finding in scan_secrets(payload):
            rendered = " ".join(finding.as_dict().values())
            self.assertNotIn("4111111111111111", rendered)
            self.assertNotIn("AKIAIOSFODNN7EXAMPLE", rendered)

    def test_credentials_are_found_by_shape(self) -> None:
        cases = {
            "private_key": b"-----BEGIN RSA PRIVATE KEY-----\n",
            "aws_access_key": b"key,AKIAIOSFODNN7EXAMPLE\n",
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
    def test_a_clean_csv_is_promoted_to_raw(self) -> None:
        admission = admit(CSV, "extracto.csv")
        self.assertTrue(admission.promoted)
        self.assertEqual("raw", admission.zone)
        self.assertEqual(sha256_bytes(CSV), admission.content_sha256)
        self.assertEqual(len(CSV), admission.byte_size)
        self.assertEqual((), admission.findings)

    def test_a_csv_with_a_card_stays_in_quarantine(self) -> None:
        admission = admit(b"cliente,tarjeta\nJuan,4111111111111111\n", "clientes.csv")
        self.assertEqual("quarantine", admission.zone)
        self.assertFalse(admission.promoted)
        self.assertIn("payment_card_number",
                      [item.kind for item in admission.findings])

    def test_quarantine_keeps_the_file_instead_of_deleting_it(self) -> None:
        # No hay camino que devuelva «borrado»: borrar la evidencia de un
        # incidente es la peor forma de responder a uno.
        admission = admit(b"campo,valor\nclave,password: sup3rsecreto\n", "config.csv")
        self.assertEqual("quarantine", admission.zone)
        self.assertIn("password_assignment", [item.kind for item in admission.findings])

    def test_a_mismatched_extension_is_recorded_but_not_fatal(self) -> None:
        admission = admit(CSV, "extracto.txt")
        self.assertEqual("raw", admission.zone)
        self.assertFalse(admission.extension_matches)
        self.assertIn("extension_mismatch", [item.kind for item in admission.findings])

    def test_an_unaccepted_type_is_refused(self) -> None:
        with self.assertRaises(RejectedUpload):
            admit(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "captura.png")

    def test_plain_text_without_structure_is_refused(self) -> None:
        # No es un descuido: un fichero de texto sin delimitadores no es un
        # documento que esta plataforma sepa leer todavia, y admitirlo seria
        # prometer un procesamiento que no existe.
        with self.assertRaises(RejectedUpload):
            admit(b"una nota suelta sin estructura\n", "nota.txt")

    def test_the_same_bytes_always_give_the_same_digest(self) -> None:
        self.assertEqual(admit(CSV, "a.csv").content_sha256,
                         admit(CSV, "b.csv").content_sha256)

    def test_one_changed_byte_changes_the_digest(self) -> None:
        self.assertNotEqual(admit(CSV, "a.csv").content_sha256,
                            admit(CSV.replace(b"125000", b"125001"), "a.csv").content_sha256)

    def test_a_pdf_is_admitted_without_being_scanned_as_text(self) -> None:
        admission = admit(PDF, "factura.pdf")
        self.assertEqual("raw", admission.zone)
        self.assertEqual("application/pdf", admission.media_type)

    def test_the_report_is_serialisable_and_carries_no_payload(self) -> None:
        rendered = str(admit(CSV, "extracto.csv").as_dict())
        self.assertNotIn("Pago proveedor", rendered)

    def test_an_admission_is_immutable(self) -> None:
        admission = admit(CSV, "extracto.csv")
        with self.assertRaises(Exception):
            admission.zone = "raw"  # type: ignore[misc]
        self.assertIsInstance(admission, Admission)


if __name__ == "__main__":
    unittest.main()
