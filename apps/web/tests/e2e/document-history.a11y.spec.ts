import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('el centro documental vacio o poblado no introduce violaciones Axe', async ({ page }) => {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.getByRole('link', { name: /Panaderia La Espiga SAS/ }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);
  await page.getByRole('link', { name: 'Documentos', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Centro de documentos' })).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
