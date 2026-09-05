"""Adaptador OCR local y acotado.

PDFium renderiza únicamente después de la validación pasiva del contrato. Cada
página viaja por stdin al binario Tesseract y su TSV vuelve por un fichero
temporal en tmpfs; no hay shell, red, nombres del cliente ni logs con texto.
"""

from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
from collections import defaultdict

from fincilia_contracts.pdf_document import (
    MAX_OCR_BLOCK_CHARS,
    MAX_PDF_BLOCKS,
    OcrBlock,
    OcrDocument,
    OcrError,
    OcrPort,
    inspect_pdf_for_ocr,
)

TESSERACT_VERSION = "5.5.1"
PDFIUM_VERSION = "5.13.0"
OCR_RELEASE = (
    f"tesseract-{TESSERACT_VERSION}/pdfium-{PDFIUM_VERSION}/fincilia-ocr-1")
OCR_LANGUAGES = ("spa", "eng")
RENDER_SCALE = 2.0
MAX_PIXELS_PER_PAGE = 16_000_000
MAX_TOTAL_PIXELS = 300_000_000
MAX_PAGE_SECONDS = 20
MAX_DOCUMENT_SECONDS = 240
MAX_PAGE_TSV_BYTES = 8 * 1024 * 1024


def _clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    if any(unicodedata.category(char) == "Cc" for char in normalized):
        raise OcrError("OCR produced control characters")
    return " ".join(normalized.split())


def _bounded(value: int, maximum: int) -> float:
    if maximum <= 0:
        raise OcrError("OCR produced an empty page dimension")
    return round(min(1.0, max(0.0, value / maximum)), 6)


def _parse_tsv(payload: bytes, *, page_number: int, width: int,
               height: int) -> list[OcrBlock]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise OcrError("Tesseract TSV is not UTF-8") from error
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    expected = {
        "level", "page_num", "block_num", "par_num", "line_num", "word_num",
        "left", "top", "width", "height", "conf", "text",
    }
    if reader.fieldnames is None or set(reader.fieldnames) != expected:
        raise OcrError("Tesseract TSV has an unexpected schema")
    lines: dict[tuple[int, int, int], list[tuple[str, int, int, int, int, float]]] = \
        defaultdict(list)
    try:
        for row in reader:
            if row["level"] != "5":
                continue
            word = _clean_text(row["text"])
            confidence = float(row["conf"])
            if not word or confidence < 0:
                continue
            left, top = int(row["left"]), int(row["top"])
            item_width, item_height = int(row["width"]), int(row["height"])
            if (left < 0 or top < 0 or item_width <= 0 or item_height <= 0
                    or left + item_width > width or top + item_height > height):
                raise OcrError("Tesseract returned a word outside the page")
            key = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
            lines[key].append(
                (word, left, top, item_width, item_height, confidence))
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise OcrError("Tesseract TSV contains an invalid value") from error

    blocks: list[OcrBlock] = []
    for ordinal, key in enumerate(sorted(lines), start=1):
        words = lines[key]
        line = " ".join(item[0] for item in words)
        if len(line) > MAX_OCR_BLOCK_CHARS:
            raise OcrError("an OCR line exceeds the accepted bound")
        x0 = min(item[1] for item in words)
        y0 = min(item[2] for item in words)
        x1 = max(item[1] + item[3] for item in words)
        y1 = max(item[2] + item[4] for item in words)
        confidence = round(sum(item[5] for item in words) / len(words) / 100, 6)
        blocks.append(OcrBlock(
            page_number, ordinal, line,
            (_bounded(x0, width), _bounded(y0, height),
             _bounded(x1, width), _bounded(y1, height)),
            min(1.0, max(0.0, confidence))))
    return blocks


class LocalTesseractOcr(OcrPort):
    """Motor local sin red, con versión y consumo máximos cerrados."""

    def __init__(self) -> None:
        executable = shutil.which("tesseract")
        if not executable:
            raise OcrError("the pinned Tesseract binary is unavailable")
        self._executable = executable

    def _verify_version(self) -> None:
        try:
            completed = subprocess.run(
                [self._executable, "--version"], check=False,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OcrError("the local OCR engine is unavailable") from error
        first = completed.stdout.decode("ascii", errors="ignore").splitlines()[:1]
        if completed.returncode != 0 or not first or not re.fullmatch(
                rf"tesseract {re.escape(TESSERACT_VERSION)}(?:\..*)?", first[0]):
            raise OcrError("the local OCR engine version is not the pinned release")

    def extract(self, payload: bytes) -> OcrDocument:
        inspection = inspect_pdf_for_ocr(payload)
        self._verify_version()
        try:
            import pypdfium2 as pdfium
        except ImportError as error:  # pragma: no cover - image invariant
            raise OcrError("the pinned local PDF renderer is unavailable") from error

        started = time.monotonic()
        total_pixels = 0
        blocks: list[OcrBlock] = []
        try:
            document = pdfium.PdfDocument(payload)
            if len(document) != inspection.page_count:
                raise OcrError("PDF render page count changed after validation")
            for page_index in range(len(document)):
                if time.monotonic() - started >= MAX_DOCUMENT_SECONDS:
                    raise OcrError("OCR exceeded the document time limit")
                page = document[page_index]
                bitmap = page.render(
                    scale=RENDER_SCALE, rotation=0, may_draw_forms=False,
                    draw_annots=False)
                image = bitmap.to_pil().convert("RGB")
                pixels = image.width * image.height
                total_pixels += pixels
                if pixels > MAX_PIXELS_PER_PAGE or total_pixels > MAX_TOTAL_PIXELS:
                    raise OcrError("OCR exceeds the pixel budget")
                encoded = io.BytesIO()
                image.save(encoded, format="PNG", optimize=False)
                with tempfile.TemporaryFile() as output:
                    try:
                        completed = subprocess.run(
                            [self._executable, "stdin", "stdout", "--dpi", "144",
                             "-l", "+".join(OCR_LANGUAGES), "--psm", "6", "tsv"],
                            input=encoded.getvalue(), stdout=output,
                            stderr=subprocess.DEVNULL, check=False,
                            timeout=min(MAX_PAGE_SECONDS, max(
                                1, int(MAX_DOCUMENT_SECONDS - (time.monotonic() - started)))),
                            env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
                    except (OSError, subprocess.TimeoutExpired) as error:
                        raise OcrError("OCR exceeded a page limit or failed locally") from error
                    if completed.returncode != 0:
                        raise OcrError("the local OCR engine rejected a rendered page")
                    size = output.tell()
                    if size <= 0 or size > MAX_PAGE_TSV_BYTES:
                        raise OcrError("the OCR page output is outside the accepted bound")
                    output.seek(0)
                    blocks.extend(_parse_tsv(
                        output.read(), page_number=page_index + 1,
                        width=image.width, height=image.height))
                    if len(blocks) > MAX_PDF_BLOCKS:
                        raise OcrError("the OCR document has too many blocks")
        except OcrError:
            raise
        except Exception as error:  # noqa: BLE001 - renderer boundary
            raise OcrError("the local PDF renderer failed closed") from error
        finally:
            closer = locals().get("document")
            if closer is not None:
                closer.close()
        if not blocks:
            raise OcrError("OCR found no usable text")
        return OcrDocument(
            inspection.artifact_sha256, OCR_RELEASE, OCR_LANGUAGES,
            inspection.page_count, tuple(blocks))
