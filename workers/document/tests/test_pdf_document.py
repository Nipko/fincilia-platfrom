from __future__ import annotations

import hashlib
import unittest
from unittest.mock import patch

from fincilia_contracts.ingestion import decide_promotion
from fincilia_contracts.pdf_document import (
    DisabledOcrPort,
    OcrBlock,
    OcrDocument,
    OcrError,
    OcrRequired,
    PdfError,
    PdfOutcome,
    deserialize_ocr_document,
    inspect_pdf,
    ocr_summary,
    sniff_pdf,
    stream_ocr_rows,
    stream_pdf_rows,
)


def build_pdf(*, text: str | None = "Fecha,Monto", active: bytes = b"") -> bytes:
    content = b"" if text is None else (
        b"BT /F1 12 Tf 72 720 Td (" + text.encode("ascii") + b") Tj ET")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R " + active + b" >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n"
        + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for ordinal, body in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{ordinal} 0 obj\n".encode("ascii"))
        payload.extend(body)
        payload.extend(b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(payload)


class PdfDocumentTests(unittest.TestCase):
    def test_safe_embedded_text_is_inspected_and_located(self) -> None:
        payload = build_pdf(text="Fecha,Monto")
        inspection, preamble = sniff_pdf(payload)
        outcome = PdfOutcome()
        rows = list(stream_pdf_rows(
            payload, preamble, outcome=outcome,
            artifact_sha256=hashlib.sha256(payload).hexdigest()))
        self.assertEqual(1, inspection.page_count)
        self.assertEqual("Fecha,Monto", rows[0].values[0])
        self.assertEqual("pdf_text", rows[0].locator(inspection.artifact_sha256)["locator_kind"])
        self.assertEqual(1, rows[0].page_number)
        self.assertEqual(1, outcome.records)

    def test_safe_pdf_is_promoted_only_after_full_inspection(self) -> None:
        decision = decide_promotion(build_pdf(), "extracto.pdf")
        self.assertTrue(decision.promoted)
        self.assertEqual("pdf", decision.internal_type)
        self.assertTrue(decision.document["requires_human_review"])
        self.assertNotIn("Fecha,Monto", repr(decision.as_dict()))

    def test_active_pdf_is_rejected(self) -> None:
        decision = decide_promotion(
            build_pdf(active=b"/OpenAction << /S /JavaScript /JS (noop) >>"),
            "activo.pdf")
        self.assertEqual("rejected", decision.decision)
        self.assertEqual("unsafe_or_active_pdf", decision.reason_code)

    def test_scanned_pdf_requires_ocr_and_stays_quarantined(self) -> None:
        decision = decide_promotion(build_pdf(text=None), "escaneado.pdf")
        self.assertEqual("quarantined", decision.decision)
        self.assertEqual("ocr_required", decision.reason_code)

    def test_envelope_and_digest_fail_closed(self) -> None:
        payload = build_pdf()
        with self.assertRaises(PdfError):
            inspect_pdf(payload[:-8])
        _, preamble = sniff_pdf(payload)
        with self.assertRaises(PdfError):
            list(stream_pdf_rows(payload, preamble, artifact_sha256="0" * 64))

    def test_ocr_port_is_disabled_without_final_configuration(self) -> None:
        with self.assertRaises(OcrRequired):
            DisabledOcrPort().extract(build_pdf(text=None))

    def test_ocr_derivative_is_canonical_and_has_exact_lineage(self) -> None:
        payload = build_pdf(text=None)
        digest = hashlib.sha256(payload).hexdigest()
        document = OcrDocument(
            digest, "tesseract-5.5.1/pdfium-5.13.0/fincilia-ocr-1",
            ("spa", "eng"), 1,
            (OcrBlock(1, 1, "Fecha Monto", (0.1, 0.2, 0.8, 0.3), 0.98),))
        serialized = document.serialize()
        self.assertEqual(document, deserialize_ocr_document(serialized))
        row = list(stream_ocr_rows(document, artifact_sha256=digest))[0]
        locator = row.locator(digest)
        self.assertEqual("pdf_ocr", locator["locator_kind"])
        self.assertEqual(document.ocr_release, locator["ocr_release"])
        self.assertNotIn("Fecha Monto", repr(document.manifest()))
        self.assertNotIn("Fecha Monto", repr(ocr_summary(document)))

    def test_ocr_can_promote_only_after_scanning_all_recognized_text(self) -> None:
        payload = build_pdf(text=None)
        digest = hashlib.sha256(payload).hexdigest()
        clean = OcrDocument(
            digest, "tesseract-5.5.1/pdfium-5.13.0/fincilia-ocr-1",
            ("spa", "eng"), 1,
            (OcrBlock(1, 1, "Fecha Monto", (0.1, 0.2, 0.8, 0.3), 0.98),))
        decision = decide_promotion(payload, "escaneado.pdf", ocr_document=clean)
        self.assertEqual("promoted", decision.decision)
        self.assertEqual("content_inspected_ocr", decision.reason_code)
        self.assertEqual("complete", decision.document["ocr_state"])
        self.assertNotIn("Fecha Monto", repr(decision.as_dict()))

        sensitive = OcrDocument(
            digest, clean.ocr_release, clean.languages, 1,
            (OcrBlock(1, 1, "4111 1111 1111 1111", (0.1, 0.2, 0.8, 0.3), 0.9),))
        denied = decide_promotion(
            payload, "escaneado.pdf", ocr_document=sensitive)
        self.assertEqual("quarantined", denied.decision)
        self.assertEqual("sensitive_content", denied.reason_code)
        self.assertNotIn("4111", repr(denied.as_dict()))

    def test_ocr_inspects_every_block_after_the_finding_cap(self) -> None:
        payload = build_pdf(text=None)
        digest = hashlib.sha256(payload).hexdigest()
        blocks = tuple(
            OcrBlock(1, index + 1,
                     "AKIA" + "A" * 16 if index < 50 else "final block",
                     (0.1, 0.1, 0.8, 0.2), 0.9)
            for index in range(51))
        document = OcrDocument(
            digest, "tesseract-5.5.1/pdfium-5.13.0/fincilia-ocr-1",
            ("eng",), 1, blocks)

        from fincilia_contracts.ingestion import scan_secrets
        with patch("fincilia_contracts.ingestion.scan_secrets",
                   wraps=scan_secrets) as scanner:
            decision = decide_promotion(
                payload, "synthetic-scanned.pdf", ocr_document=document)

        self.assertEqual("quarantined", decision.decision)
        self.assertEqual(50, len(decision.findings))
        self.assertEqual(51, scanner.call_count)

    def test_ocr_derivative_rejects_drift_and_noncanonical_json(self) -> None:
        payload = build_pdf(text=None)
        document = OcrDocument(
            hashlib.sha256(payload).hexdigest(),
            "tesseract-5.5.1/pdfium-5.13.0/fincilia-ocr-1", ("spa",), 1,
            (OcrBlock(1, 1, "sintetico", (0.1, 0.1, 0.5, 0.2), 0.9),))
        with self.assertRaises(OcrError):
            deserialize_ocr_document(document.serialize() + b"\n")
        with self.assertRaises(OcrError):
            list(stream_ocr_rows(document, artifact_sha256="0" * 64))


if __name__ == "__main__":
    unittest.main()
