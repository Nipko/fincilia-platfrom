import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { syntheticXlsx, waitForRenderedText } from './xlsx-helper';

test('la ficha perfilada de un XLSX seguro no tiene violaciones Axe', async ({ page }) => {
  test.setTimeout(120_000);
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
    name: 'movimientos-sinteticos.xlsx',
    mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    buffer: syntheticXlsx(),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);
  await waitForRenderedText(page, 'Perfil', 'hoja 1: Movimientos');

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
