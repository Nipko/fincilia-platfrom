import { expect, test, type Page } from '@playwright/test';

async function signInAndOpenCompany(page: Page): Promise<{
  companyId: string;
  sourceId: string;
}> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);
  const companyId = new URL(page.url()).pathname.split('/').at(-1)!;
  const source = page.getByLabel('Fuente del documento');
  const sourceId = await source.locator('option').filter({
    hasText: 'Extracto bancario (demo)',
  }).getAttribute('value');
  expect(sourceId).toMatch(/^[0-9a-f-]+$/);
  await source.selectOption(sourceId!);
  return { companyId, sourceId: sourceId! };
}

test('una carga queda ligada a su fuente y aparece en el centro filtrable', async ({
  page,
}) => {
  test.setTimeout(90_000);
  const marker = Date.now().toString(36);
  const filename = `historial-${marker}.csv`;
  const { companyId, sourceId } = await signInAndOpenCompany(page);

  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: filename,
    mimeType: 'text/csv',
    buffer: Buffer.from(
      `fecha,descripcion,importe\n2026-08-26,Operacion sintetica ${marker},1.00\n`,
      'utf8',
    ),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);

  await page.goto(
    `/empresas/${companyId}/documentos?fuente=${sourceId}&nombre=${marker}`,
  );
  await expect(page.getByRole('heading', { name: 'Centro de documentos' })).toBeVisible();
  await expect(page.getByRole('link', { name: filename })).toBeVisible();
  await expect(page.getByText('Extracto bancario (demo)', { exact: true }).last()).toBeVisible();
  await expect(page.getByLabel('Fuente')).toHaveValue(sourceId);
  await expect(page.getByLabel('Nombre contiene')).toHaveValue(marker);

  await page.getByLabel('Zona efectiva').selectOption('raw');
  await page.getByRole('button', { name: 'Aplicar filtros' }).click();
  await expect(page).toHaveURL(/zona=raw/);
  await expect(page.getByRole('heading', { name: 'Centro de documentos' })).toBeVisible();
});
