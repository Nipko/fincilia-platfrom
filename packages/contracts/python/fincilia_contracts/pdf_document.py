"""Inspeccion y extraccion conservadora de PDF con texto embebido.

El modulo no renderiza, no ejecuta acciones y no hace OCR. Un PDF activo,
cifrado, ambiguo o sin texto suficiente nunca se presenta como una tabla
extraida. La dependencia pesada se importa dentro de las funciones para que la
API pueda seguir usando el contrato de admision sin cargar un parser PDF.
"""

from __future__ import annotations

import hashlib
import io
import math
import re
from dataclasses import dataclass
from typing import Final, Iterator

MAX_PDF_BYTES: Final[int] = 25 * 1024 * 1024
MAX_PDF_PAGES: Final[int] = 250
MAX_PDF_OBJECTS: Final[int] = 20_000
MAX_PDF_BLOCKS: Final[int] = 200_000
MIN_EMBEDDED_TEXT_CHARS: Final[int] = 3
PARSER_RELEASE: Final[str] = "pypdf-6.16.2/fincilia-pdf-1"

OBJECT_RE = re.compile(rb"(?m)(?<!\d)(\d{1,10})\s+(\d{1,5})\s+obj\b")
ACTIVE_NAMES: Final[tuple[bytes, ...]] = (
    b"/JavaScript", b"/JS", b"/OpenAction", b"/AA", b"/Launch",
    b"/EmbeddedFile", b"/Filespec", b"/AcroForm", b"/XFA",
    b"/RichMedia", b"/SubmitForm", b"/ImportData", b"/GoToR", b"/URI",
    b"/Encrypt", b"/Sig",
)


class PdfError(ValueError):
    """El documento no cumple el perfil PDF pasivo de Fincilia."""


class OcrRequired(PdfError):
    """El PDF es pasivo, pero no contiene texto embebido utilizable."""


@dataclass(frozen=True)
class PdfInspection:
    artifact_sha256: str
    page_count: int
    object_count: int
    embedded_text_chars: int

    def manifest(self) -> dict[str, object]:
        return {
            "document_kind": "pdf",
            "artifact_sha256": self.artifact_sha256,
            "page_count": self.page_count,
            "object_count": self.object_count,
            "embedded_text": self.embedded_text_chars >= MIN_EMBEDDED_TEXT_CHARS,
            "parser_release": PARSER_RELEASE,
            "ocr_state": "not_required",
            "requires_human_review": True,
        }


@dataclass(frozen=True)
class PdfPreamble:
    artifact_sha256: str
    page_count: int
    header: tuple[str, ...]
    header_row: int = 1
    first_data_row: int = 2


@dataclass(frozen=True)
class PdfRow:
    record_ordinal: int
    page_number: int
    block_ordinal: int
    values: tuple[str, ...]
    bbox: tuple[float, float, float, float]
    confidence: float = 1.0

    def locator(self, artifact_sha256: str) -> dict[str, object]:
        return {
            "locator_kind": "pdf_text",
            "artifact_sha256": artifact_sha256,
            "record_ordinal": self.record_ordinal,
            "field_count": len(self.values),
            "page_number": self.page_number,
            "block_ordinal": self.block_ordinal,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "parser_release": PARSER_RELEASE,
        }


@dataclass
class PdfOutcome:
    records: int = 0
    pages: int = 0
    object_digest: str = ""
    record_digest: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "state": "complete",
            "truncated": False,
            "truncation_reason": None,
            "failed": False,
            "record_count": self.records,
            "row_count": max(0, self.records - 1),
            "ragged_rows": 0,
            "bytes_read": 0,
            "object_digest": self.object_digest,
            "record_digest": self.record_digest,
            "effective_encoding": "pdf-embedded-text",
            "page_count": self.pages,
            "parser_release": PARSER_RELEASE,
            "requires_human_review": True,
        }


def _name_present(payload: bytes, name: bytes) -> bool:
    return re.search(re.escape(name) + rb"(?=[\s/<>()\[\]{}%]|$)", payload) is not None


def _reader(payload: bytes):
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as error:  # pragma: no cover - packaging invariant
        raise PdfError("the pinned PDF parser is not installed") from error
    try:
        return PdfReader(io.BytesIO(payload), strict=True)
    except (PdfReadError, ValueError, TypeError, RecursionError) as error:
        raise PdfError("the PDF structure is malformed or ambiguous") from error


def _validate_envelope(payload: bytes) -> int:
    if not payload.startswith(b"%PDF-"):
        raise PdfError("the document does not have a PDF signature")
    if not payload.rstrip().endswith(b"%%EOF"):
        raise PdfError("the PDF has no unambiguous end marker")
    if not 0 < len(payload) <= MAX_PDF_BYTES:
        raise PdfError(f"the PDF exceeds the {MAX_PDF_BYTES} byte ceiling")
    object_count = len(OBJECT_RE.findall(payload))
    if object_count < 1 or object_count > MAX_PDF_OBJECTS:
        raise PdfError("the PDF object count is outside the accepted bounds")
    for name in ACTIVE_NAMES:
        if _name_present(payload, name):
            raise PdfError("active, linked, signed or encrypted PDF content is not accepted")
    return object_count


def _page_fragments(page) -> list[tuple[float, float, float, str]]:
    fragments: list[tuple[float, float, float, str]] = []

    def visitor(text, _cm, tm, _font, font_size):
        if not isinstance(text, str) or not text.strip():
            return
        try:
            x, y = float(tm[4]), float(tm[5])
            size = max(1.0, float(font_size or 1.0))
        except (TypeError, ValueError, IndexError):
            x, y, size = 0.0, 0.0, 1.0
        if not all(math.isfinite(value) for value in (x, y, size)):
            raise PdfError("the PDF exposes non-finite text coordinates")
        for line in text.replace("\r", "\n").split("\n"):
            if line.strip():
                fragments.append((y, x, size, line))

    try:
        page.extract_text(visitor_text=visitor)
    except (ValueError, TypeError, RecursionError, KeyError) as error:
        raise PdfError("embedded PDF text could not be extracted safely") from error
    return fragments


def inspect_pdf(payload: bytes) -> PdfInspection:
    object_count = _validate_envelope(payload)
    reader = _reader(payload)
    if reader.is_encrypted:
        raise PdfError("encrypted PDF content is not accepted")
    try:
        pages = reader.pages
        page_count = len(pages)
    except (ValueError, TypeError, RecursionError, KeyError) as error:
        raise PdfError("the PDF page tree is malformed") from error
    if page_count < 1 or page_count > MAX_PDF_PAGES:
        raise PdfError("the PDF page count is outside the accepted bounds")
    chars = 0
    blocks = 0
    for page in pages:
        for _, _, _, text in _page_fragments(page):
            chars += len(text.strip())
            blocks += 1
            if blocks > MAX_PDF_BLOCKS:
                raise PdfError("the PDF exposes too many text blocks")
    if chars < MIN_EMBEDDED_TEXT_CHARS:
        raise OcrRequired("the PDF requires OCR; embedded text is insufficient")
    return PdfInspection(hashlib.sha256(payload).hexdigest(), page_count,
                         object_count, chars)


def _bounded(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return round(min(1.0, max(0.0, value / maximum)), 6)


def stream_pdf_rows(payload: bytes, preamble: PdfPreamble, *,
                    outcome: PdfOutcome | None = None,
                    artifact_sha256: str) -> Iterator[PdfRow]:
    """Entrega bloques de texto con página y caja normalizada verificables."""
    if artifact_sha256 != hashlib.sha256(payload).hexdigest():
        raise PdfError("the PDF object digest does not match the artifact identity")
    inspection = inspect_pdf(payload)
    if inspection.artifact_sha256 != preamble.artifact_sha256:
        raise PdfError("the PDF preamble belongs to another artifact")
    reader = _reader(payload)
    record_digest = hashlib.sha256()
    ordinal = 0
    for page_number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width or 1)
        height = float(page.mediabox.height or 1)
        fragments = sorted(_page_fragments(page), key=lambda item: (-item[0], item[1]))
        for block_ordinal, (y, x, size, text) in enumerate(fragments, start=1):
            ordinal += 1
            x1 = x + max(size, len(text) * size * 0.5)
            y1 = y + size
            bbox = (_bounded(x, width), _bounded(y, height),
                    _bounded(x1, width), _bounded(y1, height))
            values = (text,)
            record_digest.update(
                f"{page_number}:{block_ordinal}:{bbox}:{text}".encode("utf-8"))
            yield PdfRow(ordinal, page_number, block_ordinal, values, bbox)
    if outcome is not None:
        outcome.records = ordinal
        outcome.pages = inspection.page_count
        outcome.object_digest = artifact_sha256
        outcome.record_digest = record_digest.hexdigest()


def sniff_pdf(payload: bytes) -> tuple[PdfInspection, PdfPreamble]:
    inspection = inspect_pdf(payload)
    # PDF es un workspace de bloques, no una tabla contable. El encabezado no
    # se infiere: hacerlo convertiría la primera línea en semántica financiera.
    return inspection, PdfPreamble(
        inspection.artifact_sha256, inspection.page_count, ("texto",))


def pdf_summary(preamble: PdfPreamble, outcome: PdfOutcome) -> dict[str, object]:
    result = outcome.as_dict()
    result.update({
        "header": list(preamble.header),
        "header_row": preamble.header_row,
        "first_data_row": preamble.first_data_row,
        "column_count": len(preamble.header),
        "artifact_sha256": preamble.artifact_sha256,
    })
    return result


class OcrPort:
    """Puerto deliberadamente sin proveedor: evita acoplar promoción y OCR."""

    def extract(self, _payload: bytes) -> None:
        raise NotImplementedError


class DisabledOcrPort(OcrPort):
    def extract(self, _payload: bytes) -> None:
        raise OcrRequired("OCR is disabled until provider, region and retention are approved")
