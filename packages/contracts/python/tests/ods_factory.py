from __future__ import annotations

import html
import io
import zipfile
from decimal import Decimal


def _cell(value: object, *, formula: bool = False) -> str:
    formula_attribute = ' table:formula="of:=1+1"' if formula else ""
    if isinstance(value, (int, Decimal)):
        rendered = str(value)
        return (
            f'<table:table-cell office:value-type="float" office:value="{rendered}"'
            f'{formula_attribute}><text:p>{rendered}</text:p></table:table-cell>')
    escaped = html.escape(str(value))
    return (
        f'<table:table-cell office:value-type="string"{formula_attribute}>'
        f'<text:p>{escaped}</text:p></table:table-cell>')


def _table(name: str, rows: list[list[object]], *, formula_at: tuple[int, int] | None,
           hidden: bool = False, external_link: bool = False) -> str:
    rendered_rows: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(
            _cell(value, formula=formula_at == (row_number, column))
            for column, value in enumerate(row, start=1))
        rendered_rows.append(f"<table:table-row>{cells}</table:table-row>")
    link = ('<text:p><text:a xlink:href="https://invalid.example/">externo</text:a></text:p>'
            if external_link else "")
    visible = ' table:display="false"' if hidden else ""
    return (f'<table:table table:name="{html.escape(name)}"{visible}>'
            f'{"".join(rendered_rows)}{link}</table:table>')


def build_ods(rows: list[list[object]], *,
              second_sheet: list[list[object]] | None = None,
              formula_at: tuple[int, int] | None = None,
              hidden_first: bool = False,
              external_link: bool = False,
              scripts: bool = False,
              content_override: bytes | None = None,
              encrypted: bool = False) -> bytes:
    tables = _table(
        "Movimientos", rows, formula_at=formula_at,
        hidden=hidden_first, external_link=external_link)
    if second_sheet is not None:
        tables += _table(
            "Otra", second_sheet, formula_at=None,
            hidden=False, external_link=False)
    content = content_override or (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content '
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:xlink="http://www.w3.org/1999/xlink">'
        f'<office:body><office:spreadsheet>{tables}</office:spreadsheet></office:body>'
        '</office:document-content>').encode("utf-8")
    encryption = (
        '<manifest:encryption-data manifest:checksum-type="SHA256"/>'
        if encrypted else "")
    manifest = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<manifest:manifest '
        'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">'
        '<manifest:file-entry manifest:full-path="/" '
        'manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
        '<manifest:file-entry manifest:full-path="content.xml" '
        f'manifest:media-type="text/xml">{encryption}</manifest:file-entry>'
        '</manifest:manifest>').encode("utf-8")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype", "application/vnd.oasis.opendocument.spreadsheet",
            compress_type=zipfile.ZIP_STORED)
        archive.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(
            "META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        if scripts:
            archive.writestr("Scripts/python/unsafe.py", b"pass")
    return output.getvalue()
