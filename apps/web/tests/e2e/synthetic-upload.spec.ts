import { expect, test, type Page } from '@playwright/test';

const MAX_UPLOAD_FILE_BYTES = 25 * 1024 * 1024;

async function signIn(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
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
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();

  await page.getByLabel('Fuente del documento').selectOption({ index: 1 });
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
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  await page.getByLabel('Fuente del documento').selectOption({ index: 1 });
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: 'sobre-limite-sintetico.csv',
    mimeType: 'text/csv',
    buffer: syntheticCsv(MAX_UPLOAD_FILE_BYTES + 1),
  });
  await page.getByRole('button', { name: 'Subir' }).click();

  await expect(page.getByRole('alert')).toContainText('limite de 25 MiB');
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);
});

test('el BFF conserva el 413 de la API ante un cliente que omite el precheck', async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  const companyId = new URL(page.url()).pathname.split('/').at(-1);
  const source = page.getByLabel('Fuente del documento');
  await source.selectOption({ index: 1 });
  const sourceId = await source.inputValue();
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
