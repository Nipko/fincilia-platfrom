"""Inspeccion y extraccion conservadora de PDF embebido u OCR local.

El modulo no renderiza ni ejecuta acciones. Define el contrato puro del OCR que
otro adaptador local puede producir. Un PDF activo, cifrado o ambiguo nunca se
presenta como una tabla extraida. Las dependencias pesadas se importan dentro
de las funciones para que la API no cargue motores de PDF u OCR.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
from dataclasses import dataclass
from typing import Final, Iterator, Mapping

MAX_PDF_BYTES: Final[int] = 25 * 1024 * 1024
MAX_PDF_PAGES: Final[int] = 250
MAX_PDF_OBJECTS: Final[int] = 20_000
MAX_PDF_BLOCKS: Final[int] = 200_000
MIN_EMBEDDED_TEXT_CHARS: Final[int] = 3
PARSER_RELEASE: Final[str] = "pypdf-6.16.2/fincilia-pdf-1"
OCR_SCHEMA_VERSION: Final[str] = "fincilia-pdf-ocr-1"
MAX_OCR_PAGES: Final[int] = 50
MAX_OCR_TEXT_CHARS: Final[int] = 10_000_000
MAX_OCR_BLOCK_CHARS: Final[int] = 4096

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


class OcrError(PdfError):
    """El OCR no pudo producir un derivado completo y verificable."""


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
class OcrBlock:
    page_number: int
    block_ordinal: int
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return {
            "page_number": self.page_number,
            "block_ordinal": self.block_ordinal,
            "text": self.text,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class OcrDocument:
    artifact_sha256: str
    ocr_release: str
    languages: tuple[str, ...]
    page_count: int
    blocks: tuple[OcrBlock, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", self.artifact_sha256):
            raise OcrError("the OCR artifact digest is invalid")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._/+:-]{2,119}", self.ocr_release):
            raise OcrError("the OCR release is not immutable and canonical")
        if not self.languages or any(
                not re.fullmatch(r"[a-z]{3}", item) for item in self.languages):
            raise OcrError("the OCR language set is invalid")
        if not 1 <= self.page_count <= MAX_OCR_PAGES:
            raise OcrError("the OCR page count is outside the accepted bounds")
        if not 1 <= len(self.blocks) <= MAX_PDF_BLOCKS:
            raise OcrError("the OCR block count is outside the accepted bounds")
        total_chars = 0
        last = (0, 0)
        for block in self.blocks:
            current = (block.page_number, block.block_ordinal)
            if current <= last:
                raise OcrError("OCR blocks must be strictly ordered and unique")
            last = current
            if not 1 <= block.page_number <= self.page_count:
                raise OcrError("an OCR block refers to an unknown page")
            if not 1 <= block.block_ordinal <= MAX_PDF_BLOCKS:
                raise OcrError("an OCR block ordinal is outside the accepted bounds")
            if not block.text.strip() or len(block.text) > MAX_OCR_BLOCK_CHARS:
                raise OcrError("an OCR block is empty or too large")
            if not math.isfinite(block.confidence) or not 0 <= block.confidence <= 1:
                raise OcrError("an OCR confidence is outside zero and one")
            if len(block.bbox) != 4 or any(
                    not math.isfinite(value) or not 0 <= value <= 1
                    for value in block.bbox):
                raise OcrError("an OCR box is outside the normalized page")
            x0, y0, x1, y1 = block.bbox
            if x1 <= x0 or y1 <= y0:
                raise OcrError("an OCR box has no positive area")
            total_chars += len(block.text)
            if total_chars > MAX_OCR_TEXT_CHARS:
                raise OcrError("the OCR text exceeds the accepted bound")

    def manifest(self) -> dict[str, object]:
        """Metadatos aptos para DB/job: deliberadamente no llevan texto."""
        return {
            "document_kind": "pdf",
            "artifact_sha256": self.artifact_sha256,
            "page_count": self.page_count,
            "block_count": len(self.blocks),
            "embedded_text": False,
            "parser_release": PARSER_RELEASE,
            "ocr_state": "complete",
            "ocr_release": self.ocr_release,
            "ocr_languages": list(self.languages),
            "requires_human_review": True,
        }

    def serialize(self) -> bytes:
        payload = {
            "schema_version": OCR_SCHEMA_VERSION,
            "artifact_sha256": self.artifact_sha256,
            "ocr_release": self.ocr_release,
            "languages": list(self.languages),
            "page_count": self.page_count,
            "blocks": [item.as_dict() for item in self.blocks],
        }
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")


def deserialize_ocr_document(payload: bytes) -> OcrDocument:
    """Lee exclusivamente el esquema OCR cerrado y vuelve a validar todo."""
    if not 1 <= len(payload) <= MAX_OCR_TEXT_CHARS * 2:
        raise OcrError("the OCR derivative size is outside the accepted bounds")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OcrError("the OCR derivative is not canonical JSON") from error
    if not isinstance(value, Mapping) or set(value) != {
            "schema_version", "artifact_sha256", "ocr_release", "languages",
            "page_count", "blocks"}:
        raise OcrError("the OCR derivative schema is invalid")
    if value["schema_version"] != OCR_SCHEMA_VERSION:
        raise OcrError("the OCR derivative schema version is unsupported")
    blocks = value["blocks"]
    if not isinstance(blocks, list):
        raise OcrError("the OCR derivative blocks are invalid")
    parsed: list[OcrBlock] = []
    for item in blocks:
        if not isinstance(item, Mapping) or set(item) != {
                "page_number", "block_ordinal", "text", "bbox", "confidence"}:
            raise OcrError("an OCR block schema is invalid")
        bbox = item["bbox"]
        if (not isinstance(bbox, list) or len(bbox) != 4
                or any(isinstance(v, bool) or not isinstance(v, (int, float))
                       for v in bbox)):
            raise OcrError("an OCR block box is invalid")
        if (isinstance(item["page_number"], bool)
                or not isinstance(item["page_number"], int)
                or isinstance(item["block_ordinal"], bool)
                or not isinstance(item["block_ordinal"], int)
                or not isinstance(item["text"], str)
                or isinstance(item["confidence"], bool)
                or not isinstance(item["confidence"], (int, float))):
            raise OcrError("an OCR block value has the wrong type")
        parsed.append(OcrBlock(
            item["page_number"], item["block_ordinal"], item["text"],
            tuple(float(v) for v in bbox), float(item["confidence"])))
    if (not isinstance(value["artifact_sha256"], str)
            or not isinstance(value["ocr_release"], str)
            or not isinstance(value["languages"], list)
            or any(not isinstance(item, str) for item in value["languages"])
            or isinstance(value["page_count"], bool)
            or not isinstance(value["page_count"], int)):
        raise OcrError("the OCR derivative metadata has the wrong type")
    document = OcrDocument(
        value["artifact_sha256"], value["ocr_release"],
        tuple(value["languages"]), value["page_count"], tuple(parsed))
    if document.serialize() != payload:
        raise OcrError("the OCR derivative is not canonically serialized")
    return document


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


def _inspect_pdf(payload: bytes, *, require_embedded_text: bool) -> PdfInspection:
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
    if require_embedded_text and chars < MIN_EMBEDDED_TEXT_CHARS:
        raise OcrRequired("the PDF requires OCR; embedded text is insufficient")
    return PdfInspection(hashlib.sha256(payload).hexdigest(), page_count,
                         object_count, chars)


def inspect_pdf(payload: bytes) -> PdfInspection:
    return _inspect_pdf(payload, require_embedded_text=True)


def inspect_pdf_for_ocr(payload: bytes) -> PdfInspection:
    """Valida toda la estructura pasiva sin exigir texto ya embebido."""
    inspection = _inspect_pdf(payload, require_embedded_text=False)
    if inspection.embedded_text_chars >= MIN_EMBEDDED_TEXT_CHARS:
        raise OcrError("OCR is not accepted when safe embedded text already exists")
    if inspection.page_count > MAX_OCR_PAGES:
        raise OcrError(f"OCR is limited to {MAX_OCR_PAGES} pages")
    return inspection


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


@dataclass(frozen=True)
class OcrRow:
    record_ordinal: int
    block: OcrBlock
    ocr_release: str

    @property
    def values(self) -> tuple[str, ...]:
        return (self.block.text,)

    def locator(self, artifact_sha256: str) -> dict[str, object]:
        return {
            "locator_kind": "pdf_ocr",
            "artifact_sha256": artifact_sha256,
            "record_ordinal": self.record_ordinal,
            "field_count": 1,
            "page_number": self.block.page_number,
            "block_ordinal": self.block.block_ordinal,
            "bbox": list(self.block.bbox),
            "confidence": self.block.confidence,
            "ocr_release": self.ocr_release,
        }


def stream_ocr_rows(document: OcrDocument, *,
                    artifact_sha256: str) -> Iterator[OcrRow]:
    if document.artifact_sha256 != artifact_sha256:
        raise OcrError("the OCR derivative belongs to another artifact")
    for ordinal, block in enumerate(document.blocks, start=1):
        yield OcrRow(ordinal, block, document.ocr_release)


def ocr_summary(document: OcrDocument) -> dict[str, object]:
    digest = hashlib.sha256()
    for row in stream_ocr_rows(
            document, artifact_sha256=document.artifact_sha256):
        digest.update(
            f"{row.block.page_number}:{row.block.block_ordinal}:"
            f"{row.block.bbox}:{row.block.text}".encode("utf-8"))
    return {
        "state": "complete",
        "truncated": False,
        "truncation_reason": None,
        "failed": False,
        "record_count": len(document.blocks),
        "row_count": max(0, len(document.blocks) - 1),
        "ragged_rows": 0,
        "bytes_read": 0,
        "object_digest": document.artifact_sha256,
        "record_digest": digest.hexdigest(),
        "effective_encoding": "pdf-local-ocr",
        "page_count": document.page_count,
        "ocr_release": document.ocr_release,
        "requires_human_review": True,
        "header": ["texto"],
        "header_row": 1,
        "first_data_row": 2,
        "column_count": 1,
        "artifact_sha256": document.artifact_sha256,
    }


class OcrPort:
    """Puerto deliberadamente sin proveedor: evita acoplar promoción y OCR."""

    def extract(self, _payload: bytes) -> OcrDocument:
        raise NotImplementedError


class DisabledOcrPort(OcrPort):
    def extract(self, _payload: bytes) -> OcrDocument:
        raise OcrRequired("OCR is disabled until the local isolated engine is configured")
