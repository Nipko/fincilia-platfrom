"""Constructor determinista de libros XLSX completamente sinteticos."""

from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from xml.sax.saxutils import escape


def _cell(reference: str, value: object, *, date: bool = False,
          formula: str | None = None) -> str:
    style = ' s="1"' if date else ""
    if formula is not None:
        return (f'<c r="{reference}"{style}><f>{escape(formula)}</f>'
                f'<v>{escape(str(value))}</v></c>')
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style}><v>{int(value)}</v></c>'
    if isinstance(value, (int, Decimal)):
        return f'<c r="{reference}"{style}><v>{value}</v></c>'
    return (f'<c r="{reference}" t="inlineStr"{style}><is><t xml:space="preserve">'
            f'{escape(str(value))}</t></is></c>')


def _letters(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _sheet(rows: list[list[object]], *, formula_at: tuple[int, int] | None = None,
           date_at: set[tuple[int, int]] | None = None) -> str:
    date_cells = date_at or set()
    rendered: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            reference = f"{_letters(column_number)}{row_number}"
            formula = "SUM(A1:A2)" if formula_at == (row_number, column_number) else None
            cells.append(_cell(reference, value,
                               date=(row_number, column_number) in date_cells,
                               formula=formula))
        rendered.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(rendered)}</sheetData></worksheet>')


def build_xlsx(rows: list[list[object]], *,
               second_sheet: list[list[object]] | None = None,
               formula_at: tuple[int, int] | None = None,
               date_at: set[tuple[int, int]] | None = None,
               active_part: str | None = None,
               external_relationship: bool = False,
               workbook_override: bytes | None = None,
               content_types_override: bytes | None = None) -> bytes:
    sheets = [
        '<sheet name="Movimientos" sheetId="1" r:id="rId1"/>'
    ]
    relationships = [
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
    ]
    if second_sheet is not None:
        sheets.append('<sheet name="Otra" sheetId="2" r:id="rId2"/>')
        relationships.append(
            '<Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet2.xml"/>')
    if external_relationship:
        relationships.append(
            '<Relationship Id="rId9" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/externalLinkPath" '
            'Target="https://invalid.example/book.xlsx" TargetMode="External"/>')
    workbook = workbook_override or (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{"".join(sheets)}</sheets></workbook>').encode("utf-8")
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{"".join(relationships)}</Relationships>').encode("utf-8")
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs>'
        '</styleSheet>').encode("utf-8")
    parts: dict[str, bytes] = {
        "[Content_Types].xml": content_types_override or (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            b'<Default Extension="xml" ContentType="application/xml"/>'
            b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            b'<Override PartName="/xl/workbook.xml" '
            b'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            b'</Types>'),
        "_rels/.rels": (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            b'<Relationship Id="rId1" '
            b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            b'Target="xl/workbook.xml"/></Relationships>'),
        "xl/workbook.xml": workbook,
        "xl/_rels/workbook.xml.rels": rels,
        "xl/styles.xml": styles,
        "xl/worksheets/sheet1.xml": _sheet(
            rows, formula_at=formula_at, date_at=date_at).encode("utf-8"),
    }
    if second_sheet is not None:
        parts["xl/worksheets/sheet2.xml"] = _sheet(second_sheet).encode("utf-8")
    if active_part:
        parts[active_part] = b"SYNTHETIC-ACTIVE-CONTENT"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, parts[name])
    return output.getvalue()
