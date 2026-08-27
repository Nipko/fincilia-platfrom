"""Lector XLSX determinista, sin ejecucion ni dependencias externas.

XLSX es un contenedor OPC de XML. Este modulo solo admite el subconjunto que
Fincilia puede explicar de principio a fin: hojas seleccionadas explicitamente,
sin macros, formulas, objetos activos ni relaciones externas. Lo que no entra en
ese subconjunto no se interpreta a medias; permanece en cuarentena.

Los valores salen como texto mostrado determinista. Una fecha serial con estilo
de fecha se convierte a ISO; el numero original sigue recuperable en la celda
exacta que identifica el locator. Ninguna formula se evalua y ningun XML puede
declarar DTD o entidades.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import posixpath
import re
import stat
import time
import zipfile
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR, ROUND_HALF_EVEN
from typing import Final, Iterator
from xml.etree import ElementTree as ET

MAIN_NS: Final[str] = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS: Final[str] = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
PKG_REL_NS: Final[str] = (
    "http://schemas.openxmlformats.org/package/2006/relationships")
CONTENT_TYPE_NS: Final[str] = (
    "http://schemas.openxmlformats.org/package/2006/content-types")
XLSX_MAIN_CONTENT_TYPE: Final[str] = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")

MAX_XLSX_ENTRIES: Final[int] = 512
MAX_XLSX_UNCOMPRESSED: Final[int] = 200 * 1024 * 1024
MAX_XLSX_RATIO: Final[int] = 100
MAX_XLSX_ROWS: Final[int] = 200_000
MAX_XLSX_COLUMNS: Final[int] = 512
MAX_XLSX_CELL_LENGTH: Final[int] = 4_096
MAX_SHARED_STRINGS: Final[int] = 1_000_000
MAX_XLSX_SECONDS: Final[float] = 60.0

CELL_REF = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
DATE_TOKEN = re.compile(r"(?i)(?:y+|d+|h+|s+)")
QUOTED = re.compile(r'"(?:[^"]|"")*"')
BRACKETED = re.compile(r"\[[^]]*]")
ESCAPED = re.compile(r"\\.")

BUILTIN_DATE_FORMATS: Final[frozenset[int]] = frozenset({
    14, 15, 16, 17, 18, 19, 20, 21, 22,
    27, 28, 29, 30, 31, 32, 33, 34, 35, 36,
    45, 46, 47, 50, 51, 52, 53, 54, 55, 56, 57, 58,
})

ACTIVE_PART_PREFIXES: Final[tuple[str, ...]] = (
    "xl/activex/", "xl/embeddings/", "xl/externallinks/",
    "xl/querytables/", "xl/pivotcache/", "customxml/",
)
ACTIVE_PARTS: Final[frozenset[str]] = frozenset({
    "xl/connections.xml", "xl/webpublishitems.xml", "xl/vbaproject.bin",
})

PASSIVE_PARTS: Final[frozenset[str]] = frozenset({
    "[content_types].xml", "_rels/.rels", "docprops/app.xml",
    "docprops/core.xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels",
    "xl/sharedstrings.xml", "xl/styles.xml", "xl/theme/theme1.xml",
})
PASSIVE_PART_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"^xl/worksheets/sheet[1-9][0-9]*\.xml$"),
)


class SpreadsheetError(ValueError):
    """El libro no pertenece al subconjunto seguro y explicable."""


@dataclass(frozen=True)
class Sheet:
    name: str
    sheet_id: str
    relationship_id: str
    part: str
    state: str
    ordinal: int

    @property
    def identity(self) -> str:
        material = f"{self.sheet_id}|{self.relationship_id}|{self.part}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WorkbookInspection:
    sheets: tuple[Sheet, ...]
    formula_count: int
    active_parts: tuple[str, ...]
    external_relationships: int
    uncompressed_bytes: int

    @property
    def supported(self) -> bool:
        return (len(self.sheets) == 1 and self.sheets[0].state == "visible"
                and self.formula_count == 0 and not self.active_parts
                and self.external_relationships == 0)

    def manifest(self, workbook_identity: str) -> dict[str, object]:
        """Inventario sin valores para que una persona elija la hoja.

        La identidad se deriva de relaciones OPC y no del nombre presentado. El
        manifiesto puede vivir en el resultado del escaneo porque no transcribe
        ninguna celda.
        """
        return {
            "workbook_identity": workbook_identity,
            "sheet_count": len(self.sheets),
            "sheets": [
                {
                    "sheet_identity": sheet.identity,
                    "name": sheet.name,
                    "ordinal": sheet.ordinal,
                    "state": sheet.state,
                }
                for sheet in self.sheets
            ],
        }


@dataclass(frozen=True)
class SpreadsheetPreamble:
    workbook_identity: str
    sheet_identity: str
    sheet_name: str
    sheet_ordinal: int
    sheet_part: str
    header: tuple[str, ...]
    header_row: int
    first_data_row: int
    column_count: int


@dataclass(frozen=True)
class SpreadsheetRow:
    record_ordinal: int
    values: tuple[str, ...]
    workbook_identity: str
    sheet_identity: str
    sheet_ordinal: int

    def locator(self, artifact_sha256: str) -> dict[str, object]:
        return {
            "locator_kind": "spreadsheet",
            "artifact_sha256": artifact_sha256,
            "record_ordinal": self.record_ordinal,
            "row_number": self.record_ordinal,
            "field_count": len(self.values),
            "workbook_identity": self.workbook_identity,
            "sheet_identity": self.sheet_identity,
            "sheet_ordinal": self.sheet_ordinal,
        }


@dataclass
class SpreadsheetOutcome:
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
            "effective_encoding": "xlsx-xml",
        }


def _normalised_names(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_XLSX_ENTRIES:
        raise SpreadsheetError("the workbook declares too many package entries")
    names: dict[str, zipfile.ZipInfo] = {}
    folded: set[str] = set()
    total = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        if "\x00" in name or info.flag_bits & 0x1:
            raise SpreadsheetError("the workbook contains an encrypted or invalid entry")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise SpreadsheetError("the workbook contains a symbolic-link entry")
        if info.is_dir():
            normal_dir = posixpath.normpath(name.rstrip("/"))
            if (name.startswith("/") or normal_dir.startswith("../")
                    or normal_dir == ".." or not normal_dir):
                raise SpreadsheetError("the workbook contains an unsafe package path")
            continue
        normal = posixpath.normpath(name)
        if (name.startswith("/") or normal.startswith("../") or normal == ".."
                or name != normal or not name):
            raise SpreadsheetError("the workbook contains an unsafe package path")
        key = name.casefold()
        if key in folded:
            raise SpreadsheetError("the workbook contains duplicate package paths")
        folded.add(key)
        names[name] = info
        total += info.file_size
        if total > MAX_XLSX_UNCOMPRESSED:
            raise SpreadsheetError("the workbook expands beyond the accepted ceiling")
        if (info.file_size and info.compress_size
                and info.file_size / info.compress_size > MAX_XLSX_RATIO):
            raise SpreadsheetError("a workbook part exceeds the compression ceiling")
    return names


def _read(archive: zipfile.ZipFile, names: dict[str, zipfile.ZipInfo],
          part: str) -> bytes:
    info = names.get(part)
    if info is None:
        raise SpreadsheetError(f"the workbook is missing required part {part}")
    try:
        with archive.open(info) as handle:
            payload = handle.read(info.file_size + 1)
    except (RuntimeError, NotImplementedError, zipfile.BadZipFile) as error:
        raise SpreadsheetError(f"workbook part {part} cannot be read safely") from error
    if len(payload) != info.file_size:
        raise SpreadsheetError(f"workbook part {part} changed while being read")
    return payload


def _safe_root(payload: bytes, part: str) -> ET.Element:
    # Quitar NUL permite reconocer la misma declaracion peligrosa codificada
    # como UTF-16 antes de entregar los bytes al parser.
    lowered = payload.lower().replace(b"\x00", b"")
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise SpreadsheetError(f"workbook XML part {part} declares a DTD or entity")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as error:
        raise SpreadsheetError(f"workbook XML part {part} is malformed") from error


def _relationship_target(base: str, target: str) -> str:
    candidate = target.replace("\\", "/")
    if candidate.startswith("/"):
        candidate = candidate[1:]
    else:
        candidate = posixpath.join(posixpath.dirname(base), candidate)
    normal = posixpath.normpath(candidate)
    if normal.startswith("../") or normal == "..":
        raise SpreadsheetError("a workbook relationship escapes the package")
    return normal


def inspect_workbook(payload: bytes) -> WorkbookInspection:
    """Inspecciona estructura y XML completo sin devolver valores de celdas."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as error:
        raise SpreadsheetError("the workbook is not a readable ZIP package") from error

    with archive:
        names = _normalised_names(archive)
        required = {"[Content_Types].xml", "xl/workbook.xml",
                    "xl/_rels/workbook.xml.rels"}
        if not required <= set(names):
            raise SpreadsheetError("the package is not a complete XLSX workbook")

        content_types = _safe_root(
            _read(archive, names, "[Content_Types].xml"), "[Content_Types].xml")
        workbook_types = [
            node.attrib.get("ContentType", "")
            for node in content_types.findall(f"{{{CONTENT_TYPE_NS}}}Override")
            if node.attrib.get("PartName", "").lstrip("/") == "xl/workbook.xml"
        ]
        if workbook_types != [XLSX_MAIN_CONTENT_TYPE]:
            raise SpreadsheetError(
                "the package does not declare the safe XLSX workbook content type")

        roots: dict[str, ET.Element] = {}
        external = 0
        for name in names:
            if not (name.lower().endswith(".xml") or name.lower().endswith(".rels")):
                continue
            root = _safe_root(_read(archive, names, name), name)
            roots[name] = root
            if name.lower().endswith(".rels"):
                external += sum(
                    1 for node in root.findall(f"{{{PKG_REL_NS}}}Relationship")
                    if node.attrib.get("TargetMode", "").casefold() == "external")

        rel_root = roots["xl/_rels/workbook.xml.rels"]
        targets: dict[str, str] = {}
        for node in rel_root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            rel_id = node.attrib.get("Id", "")
            target = node.attrib.get("Target", "")
            rel_type = node.attrib.get("Type", "")
            if rel_id and target and rel_type.endswith("/worksheet"):
                targets[rel_id] = _relationship_target("xl/workbook.xml", target)

        book_root = roots["xl/workbook.xml"]
        sheets: list[Sheet] = []
        for ordinal, node in enumerate(
                book_root.findall(f".//{{{MAIN_NS}}}sheet"), start=1):
            rel_id = node.attrib.get(f"{{{DOC_REL_NS}}}id", "")
            part = targets.get(rel_id, "")
            if not part or part not in names:
                raise SpreadsheetError("a declared worksheet has no package part")
            name = node.attrib.get("name", "").strip()
            sheet_id = node.attrib.get("sheetId", "").strip()
            if not name or not sheet_id:
                raise SpreadsheetError("a worksheet has no stable identity")
            sheets.append(Sheet(name=name, sheet_id=sheet_id,
                                relationship_id=rel_id, part=part,
                                state=node.attrib.get("state", "visible"),
                                ordinal=ordinal))
        if not sheets:
            raise SpreadsheetError("the workbook declares no worksheets")

        formulas = 0
        for sheet in sheets:
            root = roots.get(sheet.part)
            if root is None:
                root = _safe_root(_read(archive, names, sheet.part), sheet.part)
            formulas += len(root.findall(f".//{{{MAIN_NS}}}f"))

        active = tuple(sorted(
            name for name in names
            if name.casefold() in ACTIVE_PARTS
            or any(name.casefold().startswith(prefix)
                   for prefix in ACTIVE_PART_PREFIXES)
            or (name.casefold() not in PASSIVE_PARTS
                and not any(pattern.fullmatch(name.casefold())
                            for pattern in PASSIVE_PART_PATTERNS))))
        total = sum(info.file_size for info in names.values())
        return WorkbookInspection(tuple(sheets), formulas, active, external, total)


def iter_inspection_texts(payload: bytes) -> Iterator[tuple[str, str]]:
    """Entrega textos completos por nodo para el escaner de secretos.

    Los rich strings se concatenan antes de salir: dividir un PAN entre runs de
    formato no puede servir para ocultarlo al escaner.
    """
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = _normalised_names(archive)
        for name in sorted(names):
            if not (name.lower().endswith(".xml") or name.lower().endswith(".rels")):
                continue
            root = _safe_root(_read(archive, names, name), name)
            consumed: set[int] = set()
            for tag in (f"{{{MAIN_NS}}}si", f"{{{MAIN_NS}}}is"):
                for node in root.findall(f".//{tag}"):
                    text = "".join(item.text or "" for item in node.iter(
                        f"{{{MAIN_NS}}}t"))
                    if text:
                        yield name, text
                    consumed.update(id(item) for item in node.iter())
            for node in root.iter():
                if id(node) in consumed or not node.text or not node.text.strip():
                    continue
                yield name, node.text


def _column_number(reference: str) -> tuple[int, int]:
    match = CELL_REF.fullmatch(reference)
    if not match:
        raise SpreadsheetError("a worksheet cell has an invalid A1 reference")
    column = 0
    for char in match.group(1):
        column = column * 26 + ord(char) - 64
    row = int(match.group(2))
    if column > MAX_XLSX_COLUMNS:
        raise SpreadsheetError("a worksheet exceeds the supported column ceiling")
    if row > 1_048_576:
        raise SpreadsheetError("a worksheet row is outside XLSX bounds")
    return column, row


def column_letters(column_number: int) -> str:
    if not 1 <= column_number <= 16_384:
        raise SpreadsheetError("a spreadsheet column is outside XLSX bounds")
    letters = ""
    current = column_number
    while current:
        current, remainder = divmod(current - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def cell_a1(row_number: int, column_number: int) -> str:
    if row_number < 1:
        raise SpreadsheetError("a spreadsheet row is 1-based")
    return f"{column_letters(column_number)}{row_number}"


def _shared_strings(archive: zipfile.ZipFile,
                    names: dict[str, zipfile.ZipInfo]) -> tuple[str, ...]:
    if "xl/sharedStrings.xml" not in names:
        return ()
    root = _safe_root(_read(archive, names, "xl/sharedStrings.xml"),
                      "xl/sharedStrings.xml")
    values: list[str] = []
    for node in root.findall(f"{{{MAIN_NS}}}si"):
        if len(values) >= MAX_SHARED_STRINGS:
            raise SpreadsheetError("the workbook exceeds the shared-string ceiling")
        value = "".join(item.text or "" for item in node.iter(f"{{{MAIN_NS}}}t"))
        if len(value) > MAX_XLSX_CELL_LENGTH:
            raise SpreadsheetError("a shared string exceeds the cell ceiling")
        values.append(value)
    return tuple(values)


def _looks_like_date_format(code: str) -> bool:
    cleaned = QUOTED.sub("", code)
    cleaned = BRACKETED.sub("", cleaned)
    cleaned = ESCAPED.sub("", cleaned)
    return bool(DATE_TOKEN.search(cleaned))


def _date_styles(archive: zipfile.ZipFile,
                 names: dict[str, zipfile.ZipInfo]) -> tuple[bool, ...]:
    if "xl/styles.xml" not in names:
        return ()
    root = _safe_root(_read(archive, names, "xl/styles.xml"), "xl/styles.xml")
    custom: dict[int, str] = {}
    for node in root.findall(f".//{{{MAIN_NS}}}numFmt"):
        try:
            custom[int(node.attrib["numFmtId"])] = node.attrib.get("formatCode", "")
        except (KeyError, ValueError):
            raise SpreadsheetError("a workbook number format is invalid") from None
    cell_xfs = root.find(f"{{{MAIN_NS}}}cellXfs")
    if cell_xfs is None:
        return ()
    result: list[bool] = []
    for node in cell_xfs.findall(f"{{{MAIN_NS}}}xf"):
        try:
            format_id = int(node.attrib.get("numFmtId", "0"))
        except ValueError:
            raise SpreadsheetError("a workbook style has an invalid number format") from None
        result.append(format_id in BUILTIN_DATE_FORMATS
                      or _looks_like_date_format(custom.get(format_id, "")))
    return tuple(result)


def _date1904(archive: zipfile.ZipFile,
              names: dict[str, zipfile.ZipInfo]) -> bool:
    root = _safe_root(_read(archive, names, "xl/workbook.xml"), "xl/workbook.xml")
    props = root.find(f"{{{MAIN_NS}}}workbookPr")
    if props is None:
        return False
    return props.attrib.get("date1904", "0").casefold() in {"1", "true"}


def _serial_to_iso(value: str, *, date1904: bool) -> str:
    try:
        serial = Decimal(value)
    except InvalidOperation as error:
        raise SpreadsheetError("a date-styled cell is not numeric") from error
    whole = int(serial.to_integral_value(rounding=ROUND_FLOOR))
    fraction = serial - Decimal(whole)
    micros = int((fraction * Decimal(86_400_000_000)).to_integral_value(
        rounding=ROUND_HALF_EVEN))
    base = dt.datetime(1904, 1, 1) if date1904 else dt.datetime(1899, 12, 30)
    try:
        rendered = base + dt.timedelta(days=whole, microseconds=micros)
    except OverflowError as error:
        raise SpreadsheetError("a date serial is outside supported bounds") from error
    if micros == 0:
        return rendered.date().isoformat()
    return rendered.isoformat(timespec="microseconds").rstrip("0").rstrip(".")


def _cell_text(cell: ET.Element, shared: tuple[str, ...],
               date_styles: tuple[bool, ...], date1904: bool) -> str:
    if cell.find(f"{{{MAIN_NS}}}f") is not None:
        raise SpreadsheetError("formula cells require an explicit review flow")
    kind = cell.attrib.get("t", "n")
    if kind == "inlineStr":
        inline = cell.find(f"{{{MAIN_NS}}}is")
        value = "" if inline is None else "".join(
            item.text or "" for item in inline.iter(f"{{{MAIN_NS}}}t"))
    else:
        value_node = cell.find(f"{{{MAIN_NS}}}v")
        value = "" if value_node is None or value_node.text is None else value_node.text
        if kind == "s" and value:
            try:
                value = shared[int(value)]
            except (ValueError, IndexError):
                raise SpreadsheetError("a cell references a missing shared string") from None
        elif kind == "b" and value:
            if value not in {"0", "1"}:
                raise SpreadsheetError("a boolean cell carries an invalid value")
            value = "true" if value == "1" else "false"
        elif kind not in {"n", "str", "e", "d", "s", "b"}:
            raise SpreadsheetError(f"unsupported XLSX cell type {kind}")
        if kind == "n" and value:
            try:
                style = int(cell.attrib.get("s", "0"))
            except ValueError:
                raise SpreadsheetError("a cell has an invalid style index") from None
            if style < len(date_styles) and date_styles[style]:
                value = _serial_to_iso(value, date1904=date1904)
    if len(value) > MAX_XLSX_CELL_LENGTH:
        raise SpreadsheetError("a worksheet cell exceeds the cell ceiling")
    return value


def _rows(payload: bytes, sheet: Sheet) -> Iterator[tuple[int, tuple[str, ...]]]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = _normalised_names(archive)
        shared = _shared_strings(archive, names)
        styles = _date_styles(archive, names)
        epoch_1904 = _date1904(archive, names)
        root = _safe_root(_read(archive, names, sheet.part), sheet.part)
        previous_row = 0
        for row_node in root.findall(f".//{{{MAIN_NS}}}row"):
            cells: dict[int, str] = {}
            declared = row_node.attrib.get("r", "")
            row_number = int(declared) if declared.isdigit() else previous_row + 1
            if row_number <= previous_row or row_number < 1:
                raise SpreadsheetError("worksheet rows are duplicated or out of order")
            previous_row = row_number
            for cell in row_node.findall(f"{{{MAIN_NS}}}c"):
                reference = cell.attrib.get("r", "")
                column, referenced_row = _column_number(reference)
                if referenced_row != row_number or column in cells:
                    raise SpreadsheetError("worksheet cell references are inconsistent")
                cells[column] = _cell_text(cell, shared, styles, epoch_1904)
            if not cells:
                continue
            values = tuple(cells.get(index, "") for index in range(1, max(cells) + 1))
            if any(value.strip() for value in values):
                yield row_number, values


def sniff_workbook(
        payload: bytes, *, sheet_identity: str | None = None
        ) -> tuple[WorkbookInspection, SpreadsheetPreamble]:
    inspection = inspect_workbook(payload)
    if sheet_identity is None:
        if len(inspection.sheets) != 1:
            raise SpreadsheetError(
                "worksheet selection is required for multi-sheet books")
        sheet = inspection.sheets[0]
    else:
        sheet = next((candidate for candidate in inspection.sheets
                      if candidate.identity == sheet_identity), None)
        if sheet is None:
            raise SpreadsheetError("the selected worksheet identity does not exist")
    if sheet.state != "visible":
        raise SpreadsheetError("the selected worksheet is not visible")
    if inspection.active_parts or inspection.external_relationships:
        raise SpreadsheetError("the workbook contains active or external content")
    if inspection.formula_count:
        raise SpreadsheetError("formula cells require an explicit review flow")
    try:
        header_row, values = next(_rows(payload, sheet))
    except StopIteration:
        raise SpreadsheetError("the worksheet has no readable rows") from None
    headers = tuple(value.strip()[:120] or f"columna_{index}"
                    for index, value in enumerate(values, start=1))
    identity = hashlib.sha256(payload).hexdigest()
    return inspection, SpreadsheetPreamble(
        workbook_identity=identity, sheet_identity=sheet.identity,
        sheet_name=sheet.name, sheet_ordinal=sheet.ordinal, sheet_part=sheet.part,
        header=headers, header_row=header_row, first_data_row=header_row + 1,
        column_count=len(headers))


def stream_workbook_rows(payload: bytes, preamble: SpreadsheetPreamble, *,
                         artifact_sha256: str = "",
                         max_rows: int = MAX_XLSX_ROWS,
                         max_seconds: float = MAX_XLSX_SECONDS,
                         outcome: SpreadsheetOutcome | None = None
                         ) -> Iterator[SpreadsheetRow]:
    report = outcome if outcome is not None else SpreadsheetOutcome()
    digest = hashlib.sha256()
    object_digest = hashlib.sha256(payload).hexdigest()
    report.bytes_read = len(payload)
    report.object_digest = object_digest
    if artifact_sha256 and object_digest != artifact_sha256:
        report.state = "failed"
        report.reason = "object_digest_mismatch"
        raise SpreadsheetError("the workbook bytes do not match the artifact digest")
    inspection = inspect_workbook(payload)
    sheet = next((candidate for candidate in inspection.sheets
                  if candidate.identity == preamble.sheet_identity), None)
    if sheet is None or sheet.state != "visible":
        report.state = "failed"
        report.reason = "worksheet_identity_mismatch"
        raise SpreadsheetError("the selected worksheet is no longer available")
    if (sheet.ordinal != preamble.sheet_ordinal or sheet.part != preamble.sheet_part
            or hashlib.sha256(payload).hexdigest() != preamble.workbook_identity):
        report.state = "failed"
        report.reason = "worksheet_identity_mismatch"
        raise SpreadsheetError("the selected worksheet preamble does not match")
    started = time.monotonic()
    emitted = 0
    try:
        for row_number, values in _rows(payload, sheet):
            if time.monotonic() - started > max_seconds:
                report.state = "truncated"
                report.reason = "time_limit"
                break
            is_data = row_number >= preamble.first_data_row
            if is_data and emitted >= max_rows:
                report.state = "truncated"
                report.reason = "row_limit"
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
            suspended_at = time.monotonic()
            try:
                yield SpreadsheetRow(
                    record_ordinal=row_number, values=values,
                    workbook_identity=preamble.workbook_identity,
                    sheet_identity=preamble.sheet_identity,
                    sheet_ordinal=preamble.sheet_ordinal)
            finally:
                started += time.monotonic() - suspended_at
        if report.state == "complete" and report.data_rows == 0:
            report.state = "failed"
            report.reason = "no_data_rows"
            raise SpreadsheetError("the worksheet declares a header and no data rows")
    except SpreadsheetError:
        raise
    except Exception:
        if report.state == "complete":
            report.state = "failed"
            report.reason = "reader_error"
        raise
    finally:
        report.record_digest = digest.hexdigest()


def spreadsheet_summary(preamble: SpreadsheetPreamble,
                        outcome: SpreadsheetOutcome) -> dict[str, object]:
    return {
        "technical_format": "xlsx",
        "encoding": "xlsx-xml",
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
