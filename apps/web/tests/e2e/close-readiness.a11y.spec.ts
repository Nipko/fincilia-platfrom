import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-001 no introduce violaciones WCAG automatizadas', async ({ page }) => {
  await signInOwner(page);
  await page.goto(`/preparacion-cierre?empresa=${ESPIGA}`);
  await expect(page.getByRole('heading', { level: 1, name: 'Preparacion de cierre' }))
    .toBeVisible();
  await page.getByText('Ver evidencia por fuente', { exact: false }).first().click();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
