import { expect, test, type Page } from '@playwright/test';

import { ESPIGA } from './operations-helpers';

async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

test('FNC-CLS-005 separa preparacion y revision sin ejecutar cierre', async ({ page }) => {
  await signIn(page, 'ana@demo.local');
  await page.goto(`/preparacion-cierre?empresa=${ESPIGA}`);
  const period = page.locator('article.close-period').first();
  await expect(period).toBeVisible();
  const panel = period.getByRole('region', { name: /Expediente de revision/ });
  await expect(panel.getByText(/no contiene importes/i)).toBeVisible();
  await panel.getByRole('combobox', { name: 'Revisor independiente' })
    .selectOption({ label: 'Beto Revisor' });
  await panel.getByRole('button', { name: 'Crear expediente para revision' }).click();
  await expect(panel.getByRole('status').filter({
    hasText: /Expediente v\d+ fijado|ya existia/,
  })).toBeVisible();
  await expect(panel.locator('.close-review-list > li').first())
    .toContainText('Beto Revisor');
  await expect(page.getByRole('button', { name: /cerrar|certificar/i })).toHaveCount(0);

  await page.getByRole('button', { name: 'Salir' }).click();
  await expect(page).toHaveURL(/\/entrar$/);
  await signIn(page, 'beto@demo.local');
  await page.goto(`/preparacion-cierre?empresa=${ESPIGA}`);
  const assigned = page.locator('.close-review-list > li')
    .filter({ hasText: 'Beto Revisor' })
    .filter({ hasText: 'Pendiente de revision' }).first();
  await expect(assigned).toBeVisible();
  await assigned.getByRole('combobox', { name: 'Motivo de los cambios' })
    .selectOption('lineage_gap');
  await assigned.getByRole('button', { name: 'Solicitar cambios' }).click();
  await expect(page.locator('.close-review-list > li')
    .filter({ hasText: 'Beto Revisor' })
    .filter({ hasText: 'Cambios solicitados' })
    .filter({ hasText: 'Falta trazabilidad' }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /cerrar|certificar/i })).toHaveCount(0);
});
