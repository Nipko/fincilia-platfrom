import { deflateSync } from 'node:zlib';

const GLYPHS: Readonly<Record<string, readonly string[]>> = {
  A: ['01110', '10001', '10001', '11111', '10001', '10001', '10001'],
  C: ['01111', '10000', '10000', '10000', '10000', '10000', '01111'],
  F: ['11111', '10000', '10000', '11110', '10000', '10000', '10000'],
  I: ['11111', '00100', '00100', '00100', '00100', '00100', '11111'],
  L: ['10000', '10000', '10000', '10000', '10000', '10000', '11111'],
  N: ['10001', '11001', '10101', '10011', '10001', '10001', '10001'],
  O: ['01110', '10001', '10001', '10001', '10001', '10001', '01110'],
  R: ['11110', '10001', '10001', '11110', '10100', '10010', '10001'],
};

function rasterText(): { width: number; height: number; pixels: Buffer } {
  const width = 760;
  const height = 260;
  const scale = 14;
  const pixels = Buffer.alloc(width * height, 255);
  const draw = (text: string, startX: number, startY: number) => {
    for (const [letterIndex, letter] of [...text].entries()) {
      const glyph = GLYPHS[letter];
      if (!glyph) continue;
      for (const [row, pattern] of glyph.entries()) {
        for (const [column, bit] of [...pattern].entries()) {
          if (bit !== '1') continue;
          for (let y = 0; y < scale; y += 1) {
            for (let x = 0; x < scale; x += 1) {
              const px = startX + letterIndex * 6 * scale + column * scale + x;
              const py = startY + row * scale + y;
              pixels[py * width + px] = 0;
            }
          }
        }
      }
    }
  };
  draw('FINCILIA', 38, 24);
  draw('OCR', 250, 142);
  return { width, height, pixels };
}

function stream(dictionary: string, payload: Buffer): Buffer {
  return Buffer.concat([
    Buffer.from(`<< ${dictionary} /Length ${payload.length} >>\nstream\n`, 'ascii'),
    payload,
    Buffer.from('\nendstream', 'ascii'),
  ]);
}

export function syntheticScannedPdf(nonce: string): Buffer {
  if (!/^[a-z0-9]{1,32}$/.test(nonce)) {
    throw new Error('synthetic PDF nonce must be bounded lowercase alphanumeric text');
  }
  const { width, height, pixels } = rasterText();
  const drawing = Buffer.from('q 500 0 0 171 56 560 cm /Im0 Do Q\n', 'ascii');
  const bodies = [
    Buffer.from('<< /Type /Catalog /Pages 2 0 R >>', 'ascii'),
    Buffer.from('<< /Type /Pages /Kids [3 0 R] /Count 1 >>', 'ascii'),
    Buffer.from(
      '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] ' +
      '/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>',
      'ascii',
    ),
    stream('', drawing),
    stream(
      `/Type /XObject /Subtype /Image /Width ${width} /Height ${height} ` +
      '/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode',
      deflateSync(pixels, { level: 9 }),
    ),
  ];
  const header = Buffer.concat([
    Buffer.from('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n', 'binary'),
    Buffer.from(`% synthetic-${nonce}\n`, 'ascii'),
  ]);
  const chunks = [header];
  const offsets = [0];
  let length = header.length;
  for (const [index, body] of bodies.entries()) {
    offsets.push(length);
    const object = Buffer.concat([
      Buffer.from(`${index + 1} 0 obj\n`, 'ascii'), body,
      Buffer.from('\nendobj\n', 'ascii'),
    ]);
    chunks.push(object);
    length += object.length;
  }
  const xrefOffset = length;
  const xref = [
    `xref\n0 ${bodies.length + 1}\n`,
    '0000000000 65535 f \n',
    ...offsets.slice(1).map((offset) => `${offset.toString().padStart(10, '0')} 00000 n \n`),
    `trailer\n<< /Size ${bodies.length + 1} /Root 1 0 R >>\n`,
    `startxref\n${xrefOffset}\n%%EOF\n`,
  ].join('');
  chunks.push(Buffer.from(xref, 'ascii'));
  return Buffer.concat(chunks);
}
