import type { Page } from '@playwright/test';

type Part = { name: string; payload: Buffer };

export async function waitForRenderedText(
  page: Page,
  stableHeading: string,
  expected: string,
  timeoutMs = 60_000,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastText = '';
  while (Date.now() < deadline) {
    await page.reload({ waitUntil: 'domcontentloaded' });
    try {
      await page.getByRole('heading', { name: stableHeading, exact: true })
        .waitFor({ state: 'visible', timeout: 10_000 });
      lastText = await page.locator('body').innerText();
      if (lastText.includes(expected)) {
        return;
      }
    } catch {
      // La ruta puede estar transmitiendo `loading.tsx`; el siguiente intento
      // parte solo despues de darle tiempo a terminar, no la interrumpe en bucle.
    }
    await page.waitForTimeout(1_000);
  }
  throw new Error(
    `No aparecio ${JSON.stringify(expected)}; ultimo render: ${lastText.slice(0, 240)}`,
  );
}

function crc32(payload: Buffer): number {
  let crc = 0xffffffff;
  for (const byte of payload) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function storedZip(parts: Part[]): Buffer {
  const local: Buffer[] = [];
  const central: Buffer[] = [];
  let offset = 0;
  const date = ((2026 - 1980) << 9) | (1 << 5) | 1;

  for (const part of parts) {
    const name = Buffer.from(part.name, 'utf8');
    const checksum = crc32(part.payload);
    const header = Buffer.alloc(30);
    header.writeUInt32LE(0x04034b50, 0);
    header.writeUInt16LE(20, 4);
    header.writeUInt16LE(date, 12);
    header.writeUInt32LE(checksum, 14);
    header.writeUInt32LE(part.payload.length, 18);
    header.writeUInt32LE(part.payload.length, 22);
    header.writeUInt16LE(name.length, 26);
    local.push(header, name, part.payload);

    const directory = Buffer.alloc(46);
    directory.writeUInt32LE(0x02014b50, 0);
    directory.writeUInt16LE(20, 4);
    directory.writeUInt16LE(20, 6);
    directory.writeUInt16LE(date, 14);
    directory.writeUInt32LE(checksum, 16);
    directory.writeUInt32LE(part.payload.length, 20);
    directory.writeUInt32LE(part.payload.length, 24);
    directory.writeUInt16LE(name.length, 28);
    directory.writeUInt32LE(offset, 42);
    central.push(directory, name);
    offset += header.length + name.length + part.payload.length;
  }

  const centralPayload = Buffer.concat(central);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(parts.length, 8);
  end.writeUInt16LE(parts.length, 10);
  end.writeUInt32LE(centralPayload.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...local, centralPayload, end]);
}

function xml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function letters(column: number): string {
  let current = column;
  let result = '';
  while (current > 0) {
    const remainder = (current - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    current = Math.floor((current - 1) / 26);
  }
  return result;
}

function worksheet(rows: Array<Array<string | number>>): string {
  const sheetRows = rows.map((row, rowIndex) => {
    const cells = row.map((value, columnIndex) => {
      const reference = `${letters(columnIndex + 1)}${rowIndex + 1}`;
      return typeof value === 'number'
        ? `<c r="${reference}"><v>${value}</v></c>`
        : `<c r="${reference}" t="inlineStr"><is><t>${xml(value)}</t></is></c>`;
    });
    return `<row r="${rowIndex + 1}">${cells.join('')}</row>`;
  });
  return '<?xml version="1.0" encoding="UTF-8"?>' +
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    `<sheetData>${sheetRows.join('')}</sheetData></worksheet>`;
}

function syntheticWorkbook(
  sheets: { name: string; rows: Array<Array<string | number>> }[],
): Buffer {
  const text = (value: string): Buffer => Buffer.from(value, 'utf8');
  const workbookSheets = sheets.map((sheet, index) =>
    `<sheet name="${xml(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`,
  ).join('');
  const relationships = sheets.map((_, index) =>
    `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`,
  ).join('');
  const parts: Part[] = [
    {
      name: '[Content_Types].xml',
      payload: text('<?xml version="1.0" encoding="UTF-8"?>' +
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
        '<Default Extension="xml" ContentType="application/xml"/>' +
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
        '</Types>'),
    },
    {
      name: '_rels/.rels',
      payload: text('<?xml version="1.0" encoding="UTF-8"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
        '</Relationships>'),
    },
    {
      name: 'xl/_rels/workbook.xml.rels',
      payload: text('<?xml version="1.0" encoding="UTF-8"?>' +
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
        relationships +
        '</Relationships>'),
    },
    {
      name: 'xl/workbook.xml',
      payload: text('<?xml version="1.0" encoding="UTF-8"?>' +
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
        `<sheets>${workbookSheets}</sheets>` +
        '</workbook>'),
    },
  ];
  for (const [index, sheet] of sheets.entries()) {
    parts.push({
      name: `xl/worksheets/sheet${index + 1}.xml`,
      payload: text(worksheet(sheet.rows)),
    });
  }
  return storedZip(parts.sort((left, right) => left.name.localeCompare(right.name)));
}

export function syntheticXlsx(marker = ''): Buffer {
  const suffix = marker ? ` ${marker}` : '';
  return syntheticWorkbook([{
    name: 'Movimientos',
    rows: [
      ['Fecha', 'Descripcion', 'Importe', 'Moneda'],
      ['2026-08-01', `Pago XLSX sintetico${suffix}`, -1250, 'COP'],
      ['2026-08-02', `Abono XLSX sintetico${suffix}`, 3400, 'COP'],
    ],
  }]);
}

export function syntheticOds(marker = ''): Buffer {
  const suffix = marker ? ` ${marker}` : '';
  const rows: Array<Array<string | number>> = [
    ['Fecha', 'Descripcion', 'Importe', 'Moneda'],
    ['2026-08-01', `Pago ODS sintetico${suffix}`, -1250, 'COP'],
    ['2026-08-02', `Abono ODS sintetico${suffix}`, 3400, 'COP'],
  ];
  const tableRows = rows.map((row) => {
    const cells = row.map((value) => typeof value === 'number'
      ? `<table:table-cell office:value-type="float" office:value="${value}"><text:p>${value}</text:p></table:table-cell>`
      : `<table:table-cell office:value-type="string"><text:p>${xml(value)}</text:p></table:table-cell>`,
    ).join('');
    return `<table:table-row>${cells}</table:table-row>`;
  }).join('');
  const text = (value: string): Buffer => Buffer.from(value, 'utf8');
  return storedZip([
    {
      name: 'META-INF/manifest.xml',
      payload: text('<?xml version="1.0" encoding="UTF-8"?>' +
        '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">' +
        '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>' +
        '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>' +
        '</manifest:manifest>'),
    },
    {
      name: 'content.xml',
      payload: text('<?xml version="1.0" encoding="UTF-8"?>' +
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" ' +
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" ' +
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">' +
        '<office:body><office:spreadsheet><table:table table:name="Movimientos ODS">' +
        tableRows + '</table:table></office:spreadsheet></office:body>' +
        '</office:document-content>'),
    },
    {
      name: 'mimetype',
      payload: text('application/vnd.oasis.opendocument.spreadsheet'),
    },
  ]);
}

export function syntheticMultiSheetXlsx(marker = 'base'): Buffer {
  return syntheticWorkbook([
    {
      name: 'Resumen',
      rows: [['Resumen'], [`NO PROCESAR ESTA HOJA ${marker}`]],
    },
    {
      name: 'Movimientos del mes',
      rows: [
        ['Fecha', 'Descripcion', 'Importe', 'Moneda', 'Nota auxiliar'],
        ['2026-08-03', `Seleccion correcta XLSX ${marker}`, -2700, 'COP', 'descartar'],
        ['2026-08-04', 'Abono multihoja', 4800, 'COP', 'descartar'],
      ],
    },
  ]);
}
