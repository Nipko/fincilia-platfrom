import { expect, test, type Page } from '@playwright/test';

import {
  syntheticOds,
  syntheticMultiSheetXlsx,
  syntheticXlsx,
  waitForRenderedText,
} from './xlsx-helper';

const MAX_UPLOAD_FILE_BYTES = 25 * 1024 * 1024;
const COMPANY_URL = /\/empresas\/[0-9a-f-]+$/;

async function signIn(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

async function openSyntheticCompany(page: Page): Promise<void> {
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  // `locator.click()` no espera necesariamente a que termine una navegacion
  // del App Router. La URL es el limite observable antes de leer IDs o usar
  // controles pertenecientes a una company.
  await expect(page).toHaveURL(COMPANY_URL);
}

async function selectDemoSource(page: Page): Promise<string> {
  const source = page.getByLabel('Fuente del documento');
  const option = source.locator('option').filter({
    hasText: 'Extracto bancario (demo)',
  });
  await expect(option).toHaveCount(1);
  const sourceId = await option.getAttribute('value');
  expect(sourceId).toMatch(/^[0-9a-f-]+$/);
  await source.selectOption(sourceId!);
  return sourceId!;
}

function syntheticCsv(byteSize: number): Buffer {
  const header = Buffer.from('fecha,descripcion,importe\n', 'utf8');
  const row = Buffer.from('2026-08-01,operacion-sintetica,1.00\n', 'utf8');
  const payload = Buffer.alloc(byteSize, row);
  header.copy(payload, 0);
  return payload;
}

test('fuente → carga exacta de 25 MiB → perfil conserva contexto', async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await openSyntheticCompany(page);

  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: 'limite-exacto-sintetico.csv',
    mimeType: 'text/csv',
    buffer: syntheticCsv(MAX_UPLOAD_FILE_BYTES),
  });
  await page.getByRole('button', { name: 'Subir' }).click();

  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);
  await expect(
    page.getByRole('heading', { name: 'limite-exacto-sintetico.csv' }),
  ).toBeVisible();
  await expect(page.getByText(/Fuente seleccionada:/)).toContainText(
    'Extracto bancario (demo)',
  );
});

test('el navegador rechaza 25 MiB mas un byte sin abandonar la empresa', async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page);
  await openSyntheticCompany(page);
  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: 'sobre-limite-sintetico.csv',
    mimeType: 'text/csv',
    buffer: syntheticCsv(MAX_UPLOAD_FILE_BYTES + 1),
  });
  await page.getByRole('button', { name: 'Subir' }).click();

  await expect(
    page.getByRole('alert').filter({ hasText: 'limite de 25 MiB' }),
  ).toContainText('limite de 25 MiB');
  await expect(page).toHaveURL(COMPANY_URL);
});

test('el centro documental carga tres archivos y conserva cada expediente', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await signIn(page);
  await openSyntheticCompany(page);
  await page.getByRole('link', { name: 'Documentos', exact: true }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/documentos$/);
  await selectDemoSource(page);

  const filenames = ['banco', 'libros', 'pasarela'].map(
    (kind) => `lote-${kind}-${marker}.csv`,
  );
  await page.getByLabel('Extracto o soporte').setInputFiles(
    filenames.map((name, index) => ({
      name,
      mimeType: 'text/csv',
      buffer: Buffer.from(
        `fecha,descripcion,importe\n2026-08-0${index + 1},lote-${marker}-${index},${index + 1}.00\n`,
        'utf8',
      ),
    })),
  );
  await expect(page.getByRole('region', { name: 'Bandeja de carga' }))
    .toContainText('3 seleccionado(s)');
  await page.getByRole('button', { name: 'Subir 3' }).click();

  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/documentos$/);
  await expect(page.getByText('Completado')).toHaveCount(3);
  await expect(page.getByRole('link', { name: 'Abrir' })).toHaveCount(3);
  for (const filename of filenames) {
    await expect(page.getByRole('link', { name: filename, exact: true })).toBeVisible();
  }
});

test('el BFF conserva el 413 de la API ante un cliente que omite el precheck', async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await openSyntheticCompany(page);
  const companyId = new URL(page.url()).pathname.split('/').at(-1);
  const sourceId = await selectDemoSource(page);
  expect(companyId).toMatch(/^[0-9a-f-]+$/);
  expect(sourceId).toMatch(/^[0-9a-f-]+$/);

  const response = await page.request.post(
    `/api/companies/${companyId}/documents?sourceId=${sourceId}`,
    {
      headers: { origin: new URL(page.url()).origin },
      multipart: {
        file: {
          name: 'bypass-sintetico.csv',
          mimeType: 'text/csv',
          buffer: syntheticCsv(MAX_UPLOAD_FILE_BYTES + 1),
        },
      },
    },
  );

  expect(response.status()).toBe(413);
  await expect(response.json()).resolves.toMatchObject({ code: 'file-too-large' });
});

test('XLSX seguro de una hoja llega a perfil y vista previa con fila exacta', async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await openSyntheticCompany(page);
  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: 'movimientos-sinteticos.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticXlsx(),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);

  await waitForRenderedText(page, 'Perfil', 'hoja 1: Movimientos');
  await expect(page.getByRole('rowheader', { name: 'Descripcion' })).toBeVisible();

  await page.getByRole('link', { name: 'Mapear y publicar' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\/mapeo\?/);
  await waitForRenderedText(page, 'Extraccion', 'Pago XLSX sintetico');
  await expect(page.getByRole('rowheader', { name: '2' })).toBeVisible();
});

test('ODS seguro llega a perfil, extraccion y localizador de hoja', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await signIn(page);
  await openSyntheticCompany(page);
  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: `movimientos-ods-${marker}.ods`,
    mimeType: 'application/vnd.oasis.opendocument.spreadsheet',
    buffer: syntheticOds(marker),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);

  await waitForRenderedText(page, 'Perfil', 'hoja 1: Movimientos ODS');
  await expect(page.getByRole('rowheader', { name: 'Descripcion' })).toBeVisible();

  await page.getByRole('link', { name: 'Mapear y publicar' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\/mapeo\?/);
  await waitForRenderedText(page, 'Extraccion', `Pago ODS sintetico ${marker}`);
  await expect(page.getByRole('rowheader', { name: '2' })).toBeVisible();
});

test('XLSX multihoja exige seleccion y ofrece limpieza visual antes de mapear', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await signIn(page);
  await openSyntheticCompany(page);
  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: 'multihoja-sintetica.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticMultiSheetXlsx(marker),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);

  await waitForRenderedText(page, 'Hoja de trabajo', 'Movimientos del mes');
  await expect(page.getByRole('link', { name: 'Mapear y publicar' })).toHaveCount(0);
  await page.getByLabel(/Movimientos del mes/).check();
  await page.getByRole('button', { name: 'Usar esta hoja' }).click();
  await waitForRenderedText(page, 'Perfil', 'hoja 2: Movimientos del mes');

  await page.getByRole('link', { name: 'Mapear y publicar' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\/mapeo\?/);
  await waitForRenderedText(page, 'Extraccion', `Seleccion correcta XLSX ${marker}`);
  await expect(page.getByText('NO PROCESAR ESTA HOJA')).toHaveCount(0);
  await page.locator('#col_occurred_on').selectOption('0');
  await page.locator('#col_description').selectOption('1');
  await page.locator('#col_amount').selectOption('2');
  await page.locator('#dateFormat').selectOption('iso');
  await page.locator('#decimalFormat').selectOption('dot');
  await page.getByLabel('Nombre del mapeo').fill(`Limpieza multihoja ${marker}`);
  await page.getByLabel('Ultima fila de datos').fill('2');
  await page.getByRole('checkbox', { name: /4\. Moneda/ }).check();
  await page.getByRole('checkbox', { name: /5\. Nota auxiliar/ }).check();
  await page.getByRole('button', { name: 'Vista procesada' }).click();
  const processed = page.getByRole('region', {
    name: 'Vista procesada, aun sin guardar',
  });
  await expect(processed).toContainText('1 fila(s) en el rango');
  await expect(processed).toContainText(`Seleccion correcta XLSX ${marker}`);
  await expect(processed).not.toContainText('Abono multihoja');
  await page.getByRole('button', { name: 'Guardar mapeo' }).click();
  await expect(page.getByText(/Mapeo guardado en borrador/)).toBeVisible();
  await expect(page.getByText(/No queda nada por resolver/)).toBeVisible();
});

test('una plantilla compatible se aplica como nueva version sin reconfigurar columnas', async ({
  page,
}) => {
  test.setTimeout(180_000);
  const marker = Date.now().toString(36);
  await signIn(page);
  await openSyntheticCompany(page);
  const companyUrl = page.url();
  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: `plantilla-origen-${marker}.xlsx`,
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticXlsx(`${marker}-uno`),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);
  await waitForRenderedText(page, 'Perfil', 'hoja 1: Movimientos');
  await page.getByRole('link', { name: 'Mapear y publicar' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\/mapeo\?/);
  await waitForRenderedText(page, 'Extraccion', 'Pago XLSX sintetico');
  await page.locator('#col_occurred_on').selectOption('0');
  await page.locator('#col_description').selectOption('1');
  await page.locator('#col_amount').selectOption('2');
  await page.locator('#dateFormat').selectOption('iso');
  await page.locator('#decimalFormat').selectOption('dot');
  await page.getByLabel('Nombre del mapeo').fill(`Plantilla E2E ${marker}`);
  await page.getByRole('checkbox', { name: /4\. Moneda/ }).check();
  await page.getByRole('button', { name: 'Guardar mapeo' }).click();
  await expect(page.getByText(/Mapeo guardado en borrador/)).toBeVisible();

  await page.goto(companyUrl);
  await selectDemoSource(page);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: `plantilla-destino-${marker}.xlsx`,
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticXlsx(`${marker}-dos`),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);
  await waitForRenderedText(page, 'Perfil', 'hoja 1: Movimientos');
  await page.getByRole('link', { name: 'Mapear y publicar' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\/mapeo\?/);
  await waitForRenderedText(page, 'Extraccion', 'Pago XLSX sintetico');

  const library = page.getByRole('navigation', { name: 'Plantillas reutilizables' });
  await expect(library).toContainText('compatible');
  await library.getByRole('link', {
    name: `Usar Plantilla E2E ${marker}`,
  }).click();
  await expect(page).toHaveURL(/plantilla=[0-9a-f-]+/);
  await expect(page.getByText(/Crearas la version 2/)).toBeVisible();
  await expect(page.locator('#col_occurred_on')).toHaveValue('0');
  await expect(page.locator('#col_description')).toHaveValue('1');
  await expect(page.locator('#col_amount')).toHaveValue('2');
  await page.getByRole('button', { name: 'Vista procesada' }).click();
  await expect(page.getByRole('region', {
    name: 'Vista procesada, aun sin guardar',
  })).toContainText(`Pago XLSX sintetico ${marker}-dos`);
  await page.getByRole('button', { name: 'Guardar nueva version' }).click();
  await expect(page.getByText(/Mapeo guardado en borrador/)).toBeVisible();
});
