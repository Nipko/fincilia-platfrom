import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-WEB-005 superficies parciales conservan accesibilidad', async ({ page }) => {
  await signInOwner(page);
  const paths = [
    '/cuenta',
    `/recordatorios?empresa=${ESPIGA}`,
    '/calidad',
    `/empresas/${ESPIGA}/documentos`,
  ];

  for (const path of paths) {
    await page.goto(path);
    await expect(page.locator('main')).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `violaciones en ${path}`).toEqual([]);
  }
});
