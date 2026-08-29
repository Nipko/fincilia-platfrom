"""Lector ODS determinista para el subconjunto tabular seguro de Fincilia.

ODS es un ZIP de XML, no una promesa de que el contenido sea pasivo. Este
modulo solo acepta paquetes pequenos y explicables: texto y valores escalares
en hojas visibles, sin formulas, scripts, enlaces, objetos, cifrado ni partes
binarias. Nada se ejecuta y cualquier estructura que no podamos explicar queda
en cuarentena antes de que el worker la transcriba.
"""

from __future__ import annotations

import hashlib
import io
import posixpath
import stat
import time
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Iterator
from xml.etree import ElementTree as ET

from .spreadsheet import (
    Sheet,
    SpreadsheetPreamble,
    SpreadsheetRow,
    WorkbookInspection,
)

OFFICE_NS: Final[str] = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
TABLE_NS: Final[str] = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
TEXT_NS: Final[str] = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
XLINK_NS: Final[str] = "http://www.w3.org/1999/xlink"
MANIFEST_NS: Final[str] = "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"

ODS_MIMETYPE: Final[bytes] = b"application/vnd.oasis.opendocument.spreadsheet"
MAX_ODS_ENTRIES: Final[int] = 128
MAX_ODS_UNCOMPRESSED: Final[int] = 200 * 1024 * 1024
MAX_ODS_RATIO: Final[int] = 100
MAX_ODS_ROWS: Final[int] = 200_000
MAX_ODS_COLUMNS: Final[int] = 512
MAX_ODS_CELL_LENGTH: Final[int] = 4_096
MAX_ODS_SECONDS: Final[float] = 60.0

REQUIRED_PARTS: Final[frozenset[str]] = frozenset({
    "mimetype", "content.xml", "META-INF/manifest.xml",
})
PASSIVE_PARTS: Final[frozenset[str]] = frozenset({
    "mimetype", "content.xml", "styles.xml", "meta.xml", "settings.xml",
    "META-INF/manifest.xml",
})
ACTIVE_TAGS: Final[frozenset[str]] = frozenset({
    "applet", "event-listeners", "forms", "frame", "image", "object",
    "object-ole", "plugin", "script", "scripts",
})


class OpenDocumentError(ValueError):
    """El ODS no pertenece al subconjunto pasivo y reproducible."""


@dataclass
class OpenDocumentOutcome:
    state: str = "complete"
    reason: str | None = None
    records: int = 0
    data_rows: int = 0
    ragged_rows: int = 0
    bytes_read: int = 0
    object_digest: str = ""
    record_digest: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "truncation_reason": self.reason,
            "truncated": self.state == "truncated",
            "failed": self.state == "failed",
            "record_count": self.records,
            "row_count": self.data_rows,
            "ragged_rows": self.ragged_rows,
            "bytes_read": self.bytes_read,
            "object_digest": self.object_digest,
            "record_digest": self.record_digest,
            "effective_encoding": "ods-xml",
        }


def _normalised_names(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_ODS_ENTRIES:
        raise OpenDocumentError("the document declares too many package entries")
    names: dict[str, zipfile.ZipInfo] = {}
    folded: set[str] = set()
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if "\x00" in name or info.flag_bits & 0x1:
            raise OpenDocumentError("the document contains an encrypted or invalid entry")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise OpenDocumentError("the document contains a symbolic-link entry")
        if info.is_dir():
            normal_dir = posixpath.normpath(name.rstrip("/"))
            if (name.startswith("/") or normal_dir.startswith("../")
                    or normal_dir in {"", ".."}):
                raise OpenDocumentError("the document contains an unsafe package path")
            continue
        normal = posixpath.normpath(name)
        if (name.startswith("/") or normal.startswith("../") or normal == ".."
                or name != normal or not name):
            raise OpenDocumentError("the document contains an unsafe package path")
        key = name.casefold()
        if key in folded:
            raise OpenDocumentError("the document contains duplicate package paths")
        folded.add(key)
        names[name] = info
        total += info.file_size
        if info.file_size and info.compress_size:
            if info.file_size / info.compress_size > MAX_ODS_RATIO:
                raise OpenDocumentError("a document part exceeds the compression ceiling")
    if total > MAX_ODS_UNCOMPRESSED:
        raise OpenDocumentError("the document expands beyond the byte ceiling")
    return names


def _read(archive: zipfile.ZipFile, names: dict[str, zipfile.ZipInfo], part: str) -> bytes:
    info = names.get(part)
    if info is None:
        raise OpenDocumentError(f"the document is missing {part}")
    with archive.open(info) as handle:
        payload = handle.read(info.file_size + 1)
    if len(payload) != info.file_size:
        raise OpenDocumentError("a document part changed size while being read")
    return payload


def _safe_root(payload: bytes, part: str) -> ET.Element:
    lowered = payload[:4096].lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise OpenDocumentError(f"{part} declares a DTD or entity")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as error:
        raise OpenDocumentError(f"{part} is not well-formed XML") from error


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _repeat(node: ET.Element, name: str) -> int:
    raw = node.attrib.get(f"{{{TABLE_NS}}}{name}", "1")
    if not raw.isdigit() or int(raw) < 1:
        raise OpenDocumentError("the document declares an invalid repetition")
    return int(raw)


def _rich_text(node: ET.Element) -> str:
    pieces: list[str] = []

    def visit(current: ET.Element) -> None:
        if current.text:
            pieces.append(current.text)
        for child in current:
            local = _local_name(child.tag)
            if child.tag == f"{{{TEXT_NS}}}s":
                count = child.attrib.get(f"{{{TEXT_NS}}}c", "1")
                if not count.isdigit() or int(count) > MAX_ODS_CELL_LENGTH:
                    raise OpenDocumentError("the document declares unsafe text spacing")
                pieces.append(" " * int(count))
            elif child.tag == f"{{{TEXT_NS}}}tab":
                pieces.append("\t")
            elif child.tag == f"{{{TEXT_NS}}}line-break":
                pieces.append("\n")
            else:
                if local in ACTIVE_TAGS:
                    raise OpenDocumentError("the document contains active cell content")
                visit(child)
            if child.tail:
                pieces.append(child.tail)

    visit(node)
    value = "".join(pieces)
    if len(value) > MAX_ODS_CELL_LENGTH:
        raise OpenDocumentError("a document cell exceeds the text ceiling")
    return value


def _cell_text(cell: ET.Element) -> str:
    if f"{{{TABLE_NS}}}formula" in cell.attrib:
        raise OpenDocumentError("formula cells require an explicit review flow")
    if (_repeat(cell, "number-columns-spanned") != 1
            or _repeat(cell, "number-rows-spanned") != 1):
        raise OpenDocumentError("merged cells are outside the supported subset")
    value_type = cell.attrib.get(f"{{{OFFICE_NS}}}value-type", "")
    if value_type in {"float", "currency", "percentage"}:
        raw = cell.attrib.get(f"{{{OFFICE_NS}}}value", "")
        try:
            value = format(Decimal(raw), "f")
        except InvalidOperation as error:
            raise OpenDocumentError("a numeric cell is not an exact decimal") from error
    elif value_type == "date":
        value = cell.attrib.get(f"{{{OFFICE_NS}}}date-value", "")
    elif value_type == "time":
        value = cell.attrib.get(f"{{{OFFICE_NS}}}time-value", "")
    elif value_type == "boolean":
        value = cell.attrib.get(f"{{{OFFICE_NS}}}boolean-value", "")
    else:
        paragraphs = cell.findall(f".//{{{TEXT_NS}}}p")
        value = "\n".join(_rich_text(item) for item in paragraphs)
        if not value:
            value = cell.attrib.get(f"{{{OFFICE_NS}}}string-value", "")
    if len(value) > MAX_ODS_CELL_LENGTH:
        raise OpenDocumentError("a document cell exceeds the text ceiling")
    return value


def _package(payload: bytes) -> tuple[dict[str, zipfile.ZipInfo], dict[str, ET.Element]]:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = _normalised_names(archive)
            missing = REQUIRED_PARTS - set(names)
            if missing:
                raise OpenDocumentError("the package is missing required ODS parts")
            if _read(archive, names, "mimetype") != ODS_MIMETYPE:
                raise OpenDocumentError("the package does not declare the ODS mimetype")
            roots = {
                name: _safe_root(_read(archive, names, name), name)
                for name in names if name.endswith(".xml")
            }
    except zipfile.BadZipFile as error:
        raise OpenDocumentError("the ODS package is not readable") from error
    manifest = roots["META-INF/manifest.xml"]
    if manifest.findall(f".//{{{MANIFEST_NS}}}encryption-data"):
        raise OpenDocumentError("encrypted ODS documents are not supported")
    return names, roots


def inspect_open_document(payload: bytes) -> WorkbookInspection:
    names, roots = _package(payload)
    active_parts = sorted(set(names) - PASSIVE_PARTS)
    formula_count = 0
    external = 0
    for part, root in roots.items():
        for node in root.iter():
            local = _local_name(node.tag)
            if local in ACTIVE_TAGS:
                active_parts.append(f"{part}#{local}")
            if f"{{{TABLE_NS}}}formula" in node.attrib:
                formula_count += 1
            href = node.attrib.get(f"{{{XLINK_NS}}}href")
            if href and not href.startswith("#"):
                external += 1
            if (_repeat(node, "number-columns-spanned") != 1
                    or _repeat(node, "number-rows-spanned") != 1):
                active_parts.append(f"{part}#merged-cell")

    content = roots["content.xml"]
    spreadsheet = content.find(
        f"./{{{OFFICE_NS}}}body/{{{OFFICE_NS}}}spreadsheet")
    if spreadsheet is None:
        raise OpenDocumentError("content.xml does not contain a spreadsheet")
    sheets: list[Sheet] = []
    seen_names: set[str] = set()
    for ordinal, table in enumerate(
            spreadsheet.findall(f"{{{TABLE_NS}}}table"), start=1):
        name = table.attrib.get(f"{{{TABLE_NS}}}name", "").strip()
        if not name or name in seen_names or len(name) > 120:
            raise OpenDocumentError("worksheet names are missing, duplicated or too long")
        seen_names.add(name)
        state = ("hidden" if table.attrib.get(f"{{{TABLE_NS}}}display", "true")
                 == "false" else "visible")
        sheets.append(Sheet(
            name=name, sheet_id=str(ordinal), relationship_id="ods-table",
            part=f"content.xml#table-{ordinal}", state=state, ordinal=ordinal))
    if not sheets:
        raise OpenDocumentError("the document has no worksheets")
    return WorkbookInspection(
        sheets=tuple(sheets), formula_count=formula_count,
        active_parts=tuple(sorted(set(active_parts))),
        external_relationships=external,
        uncompressed_bytes=sum(info.file_size for info in names.values()))


def _table(payload: bytes, sheet: Sheet) -> ET.Element:
    _, roots = _package(payload)
    spreadsheet = roots["content.xml"].find(
        f"./{{{OFFICE_NS}}}body/{{{OFFICE_NS}}}spreadsheet")
    if spreadsheet is None:
        raise OpenDocumentError("content.xml does not contain a spreadsheet")
    tables = spreadsheet.findall(f"{{{TABLE_NS}}}table")
    if sheet.ordinal > len(tables):
        raise OpenDocumentError("the selected worksheet no longer exists")
    return tables[sheet.ordinal - 1]


def _rows(payload: bytes, sheet: Sheet) -> Iterator[tuple[int, tuple[str, ...]]]:
    table = _table(payload, sheet)
    row_number = 0
    for row_node in table.findall(f"{{{TABLE_NS}}}table-row"):
        row_repeat = _repeat(row_node, "number-rows-repeated")
        if row_number + row_repeat > MAX_ODS_ROWS:
            raise OpenDocumentError("the document exceeds the row ceiling")
        values: list[str] = []
        for cell in row_node:
            if cell.tag not in {
                    f"{{{TABLE_NS}}}table-cell",
                    f"{{{TABLE_NS}}}covered-table-cell"}:
                continue
            value = "" if cell.tag.endswith("covered-table-cell") else _cell_text(cell)
            repeat = _repeat(cell, "number-columns-repeated")
            if value and len(values) + repeat > MAX_ODS_COLUMNS:
                raise OpenDocumentError("the document exceeds the column ceiling")
            remaining = max(0, MAX_ODS_COLUMNS - len(values))
            values.extend([value] * min(repeat, remaining))
        while values and not values[-1].strip():
            values.pop()
        if values and any(value.strip() for value in values):
            for offset in range(row_repeat):
                yield row_number + offset + 1, tuple(values)
        row_number += row_repeat


def iter_open_document_texts(payload: bytes) -> Iterator[tuple[str, str]]:
    """Texto logico para PAN/secretos; nunca devuelve XML ni formulas."""
    inspection = inspect_open_document(payload)
    if inspection.active_parts or inspection.external_relationships:
        raise OpenDocumentError("the document contains active or external content")
    for sheet in inspection.sheets:
        for row_number, values in _rows(payload, sheet):
            for column, value in enumerate(values, start=1):
                if value:
                    yield f"{sheet.name}!R{row_number}C{column}", value
    _, roots = _package(payload)
    for part in ("meta.xml", "settings.xml", "styles.xml"):
        root = roots.get(part)
        if root is not None:
            text = " ".join(item.strip() for item in root.itertext() if item.strip())
            if text:
                yield part, text


def sniff_open_document(
        payload: bytes, *, sheet_identity: str | None = None
        ) -> tuple[WorkbookInspection, SpreadsheetPreamble]:
    inspection = inspect_open_document(payload)
    if inspection.active_parts or inspection.external_relationships:
        raise OpenDocumentError("the document contains active or external content")
    if inspection.formula_count:
        raise OpenDocumentError("formula cells require an explicit review flow")
    if sheet_identity is None:
        if len(inspection.sheets) != 1:
            raise OpenDocumentError("worksheet selection is required for multi-sheet documents")
        sheet = inspection.sheets[0]
    else:
        sheet = next((candidate for candidate in inspection.sheets
                      if candidate.identity == sheet_identity), None)
        if sheet is None:
            raise OpenDocumentError("the selected worksheet identity does not exist")
    if sheet.state != "visible":
        raise OpenDocumentError("the selected worksheet is not visible")
    try:
        header_row, values = next(_rows(payload, sheet))
    except StopIteration:
        raise OpenDocumentError("the worksheet has no readable rows") from None
    headers = tuple(value.strip()[:120] or f"columna_{index}"
                    for index, value in enumerate(values, start=1))
    identity = hashlib.sha256(payload).hexdigest()
    return inspection, SpreadsheetPreamble(
        workbook_identity=identity, sheet_identity=sheet.identity,
        sheet_name=sheet.name, sheet_ordinal=sheet.ordinal, sheet_part=sheet.part,
        header=headers, header_row=header_row, first_data_row=header_row + 1,
        column_count=len(headers))


def stream_open_document_rows(
        payload: bytes, preamble: SpreadsheetPreamble, *, artifact_sha256: str = "",
        max_rows: int = MAX_ODS_ROWS, max_seconds: float = MAX_ODS_SECONDS,
        outcome: OpenDocumentOutcome | None = None) -> Iterator[SpreadsheetRow]:
    report = outcome if outcome is not None else OpenDocumentOutcome()
    digest = hashlib.sha256()
    object_digest = hashlib.sha256(payload).hexdigest()
    report.bytes_read = len(payload)
    report.object_digest = object_digest
    if artifact_sha256 and object_digest != artifact_sha256:
        report.state, report.reason = "failed", "object_digest_mismatch"
        raise OpenDocumentError("the document bytes do not match the artifact digest")
    inspection = inspect_open_document(payload)
    sheet = next((candidate for candidate in inspection.sheets
                  if candidate.identity == preamble.sheet_identity), None)
    if (sheet is None or sheet.state != "visible" or sheet.ordinal != preamble.sheet_ordinal
            or sheet.part != preamble.sheet_part
            or object_digest != preamble.workbook_identity):
        report.state, report.reason = "failed", "worksheet_identity_mismatch"
        raise OpenDocumentError("the selected worksheet preamble does not match")
    if inspection.active_parts or inspection.external_relationships or inspection.formula_count:
        report.state, report.reason = "failed", "unsafe_document_content"
        raise OpenDocumentError("the document is no longer in the supported subset")
    started = time.monotonic()
    emitted = 0
    try:
        for row_number, values in _rows(payload, sheet):
            if time.monotonic() - started > max_seconds:
                report.state, report.reason = "truncated", "time_limit"
                break
            is_data = row_number >= preamble.first_data_row
            if is_data and emitted >= max_rows:
                report.state, report.reason = "truncated", "row_limit"
                break
            digest.update(f"{row_number}:{len(values)}|".encode("ascii"))
            for value in values:
                encoded = value.encode("utf-8", "surrogatepass")
                digest.update(f"{len(encoded)}:".encode("ascii"))
                digest.update(encoded)
            report.records += 1
            if is_data:
                emitted += 1
                report.data_rows = emitted
                if len(values) != preamble.column_count:
                    report.ragged_rows += 1
            suspended = time.monotonic()
            try:
                yield SpreadsheetRow(
                    record_ordinal=row_number, values=values,
                    workbook_identity=preamble.workbook_identity,
                    sheet_identity=preamble.sheet_identity,
                    sheet_ordinal=preamble.sheet_ordinal)
            finally:
                started += time.monotonic() - suspended
        if report.state == "complete" and report.data_rows == 0:
            report.state, report.reason = "failed", "no_data_rows"
            raise OpenDocumentError("the worksheet declares a header and no data rows")
    except OpenDocumentError:
        raise
    except Exception:
        if report.state == "complete":
            report.state, report.reason = "failed", "reader_error"
        raise
    finally:
        report.record_digest = digest.hexdigest()


def open_document_summary(
        preamble: SpreadsheetPreamble,
        outcome: OpenDocumentOutcome) -> dict[str, object]:
    return {
        "technical_format": "ods",
        "encoding": "ods-xml",
        "delimiter": "",
        "header": list(preamble.header),
        "header_row": preamble.header_row,
        "first_data_row": preamble.first_data_row,
        "column_count": preamble.column_count,
        "sheet_name": preamble.sheet_name,
        "sheet_ordinal": preamble.sheet_ordinal,
        "workbook_identity": preamble.workbook_identity,
        **outcome.as_dict(),
    }
