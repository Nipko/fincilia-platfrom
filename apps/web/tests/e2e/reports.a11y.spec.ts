import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { signInOwner } from './operations-helpers';

test('FNC-RPT-001 centro de informes sin violaciones WCAG automatizadas', async ({ page }) => {
  await signInOwner(page);
  await page.goto('/informes?dias=365');
  await expect(page.getByRole('heading', { level: 1, name: 'Informes e historicos' }))
    .toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
