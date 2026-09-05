from __future__ import annotations

import io
import unittest

from fincilia_contracts.pdf_document import OcrError
from fincilia_worker.local_ocr import (
    LocalTesseractOcr,
    OCR_RELEASE,
    _parse_tsv,
)


def build_scanned_pdf(text: str = "FINCILIA SYNTHETIC TOTAL 1250") -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1600, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=72)
    draw.text((80, 180), text, fill="black", font=font)
    output = io.BytesIO()
    image.save(output, format="PDF", resolution=144.0)
    return output.getvalue()


class TsvContractTests(unittest.TestCase):
    def test_words_are_grouped_into_lines_without_losing_coordinates(self) -> None:
        header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        body = (
            "5\t1\t1\t1\t1\t1\t10\t20\t30\t10\t90\tFecha\n"
            "5\t1\t1\t1\t1\t2\t50\t20\t40\t10\t80\tMonto\n")
        blocks = _parse_tsv(
            (header + body).encode(), page_number=1, width=100, height=100)
        self.assertEqual(1, len(blocks))
        self.assertEqual("Fecha Monto", blocks[0].text)
        self.assertEqual((0.1, 0.2, 0.9, 0.3), blocks[0].bbox)
        self.assertEqual(0.85, blocks[0].confidence)

    def test_out_of_page_tsv_fails_closed(self) -> None:
        payload = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t90\t20\t30\t10\t90\tFuera\n").encode()
        with self.assertRaises(OcrError):
            _parse_tsv(payload, page_number=1, width=100, height=100)


class LocalOcrIntegrationTests(unittest.TestCase):
    def test_image_only_pdf_is_read_by_the_pinned_local_engine(self) -> None:
        document = LocalTesseractOcr().extract(build_scanned_pdf())
        self.assertEqual(OCR_RELEASE, document.ocr_release)
        self.assertEqual(1, document.page_count)
        recognized = " ".join(block.text for block in document.blocks).upper()
        self.assertIn("FINCILIA", recognized)
        self.assertIn("SYNTHETIC", recognized)
        self.assertNotIn("FINCILIA", repr(document.manifest()))


if __name__ == "__main__":
    unittest.main()
