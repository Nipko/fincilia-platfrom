from __future__ import annotations

import hashlib
import unittest

from fincilia_contracts.ingestion import decide_promotion
from fincilia_contracts.pdf_document import (
    DisabledOcrPort,
    OcrRequired,
    PdfError,
    PdfOutcome,
    inspect_pdf,
    sniff_pdf,
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


if __name__ == "__main__":
    unittest.main()
