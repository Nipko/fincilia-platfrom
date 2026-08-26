import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { ESPIGA } from './operations-helpers';

test('FNC-CLS-005 conserva accesibilidad en el expediente de revision', async ({ page }) => {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
  await page.goto(`/preparacion-cierre?empresa=${ESPIGA}`);
  const panel = page.getByRole('region', { name: /Expediente de revision/ }).first();
  await expect(panel).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
