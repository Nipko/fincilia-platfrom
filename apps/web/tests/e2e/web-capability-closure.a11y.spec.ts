import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-WEB-005 superficies parciales conservan accesibilidad', async ({ page }) => {
  await signInOwner(page);
  const paths = [
    { path: '/cuenta', heading: 'Tu cuenta' },
    {
      path: `/recordatorios?empresa=${ESPIGA}`,
      heading: 'Centro de ciclos y recordatorios',
    },
    { path: '/calidad', heading: 'Centro de calidad' },
    {
      path: `/empresas/${ESPIGA}/documentos`,
      heading: 'Centro de documentos',
    },
  ];

  for (const { path, heading } of paths) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
    await expect(page.getByRole('main')).toHaveCount(1);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations, `violaciones en ${path}`).toEqual([]);
  }
});
