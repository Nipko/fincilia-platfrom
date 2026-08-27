import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import {
  syntheticMultiSheetXlsx,
  syntheticXlsx,
  waitForRenderedText,
} from './xlsx-helper';

test('la ficha perfilada de un XLSX seguro no tiene violaciones Axe', async ({ page }) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);

  const source = page.getByLabel('Fuente del documento');
  const sourceId = await source.locator('option').filter({
    hasText: 'Extracto bancario (demo)',
  }).getAttribute('value');
  expect(sourceId).toMatch(/^[0-9a-f-]+$/);
  await source.selectOption(sourceId!);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: `movimientos-accesibles-${marker}.xlsx`,
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticXlsx(marker),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);
  await waitForRenderedText(page, 'Perfil', 'hoja 1: Movimientos');

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);

  await page.getByRole('link', { name: 'Mapear y publicar' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\/mapeo\?/);
  await waitForRenderedText(page, 'Extraccion', `Pago XLSX sintetico ${marker}`);
  await page.locator('#col_occurred_on').selectOption('0');
  await page.locator('#col_description').selectOption('1');
  await page.locator('#col_amount').selectOption('2');
  await page.locator('#dateFormat').selectOption('iso');
  await page.locator('#decimalFormat').selectOption('dot');
  await page.getByRole('checkbox', { name: /4\. Moneda/ }).check();
  await page.getByRole('button', { name: 'Vista procesada' }).click();
  await expect(page.getByRole('region', {
    name: 'Vista procesada, aun sin guardar',
  })).toBeVisible();
  const mappingResults = await new AxeBuilder({ page }).analyze();
  expect(mappingResults.violations).toEqual([]);
});

test('el selector multihoja y su estado pendiente no tienen violaciones Axe', async ({ page }) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  const source = page.getByLabel('Fuente del documento');
  const sourceId = await source.locator('option').filter({
    hasText: 'Extracto bancario (demo)',
  }).getAttribute('value');
  await source.selectOption(sourceId!);
  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: 'multihoja-accesible.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticMultiSheetXlsx(marker),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);
  await waitForRenderedText(page, 'Hoja de trabajo', 'Movimientos del mes');

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test('la bandeja multiple antes y despues de cargar no tiene violaciones Axe', async ({
  page,
}) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  await page.getByRole('link', { name: 'Documentos', exact: true }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/documentos$/);

  const source = page.getByLabel('Fuente del documento');
  const sourceId = await source.locator('option').filter({
    hasText: 'Extracto bancario (demo)',
  }).getAttribute('value');
  await source.selectOption(sourceId!);
  await page.getByLabel('Extracto o soporte').setInputFiles([
    {
      name: `accesible-a-${marker}.csv`,
      mimeType: 'text/csv',
      buffer: Buffer.from(
        `fecha,descripcion,importe\n2026-08-01,accesible-${marker}-a,1.00\n`,
      ),
    },
    {
      name: `accesible-b-${marker}.csv`,
      mimeType: 'text/csv',
      buffer: Buffer.from(
        `fecha,descripcion,importe\n2026-08-02,accesible-${marker}-b,2.00\n`,
      ),
    },
  ]);

  const queued = await new AxeBuilder({ page }).analyze();
  expect(queued.violations).toEqual([]);

  await page.getByRole('button', { name: 'Subir 2' }).click();
  await expect(page.getByText('Completado')).toHaveCount(2);
  const completed = await new AxeBuilder({ page }).analyze();
  expect(completed.violations).toEqual([]);
});
