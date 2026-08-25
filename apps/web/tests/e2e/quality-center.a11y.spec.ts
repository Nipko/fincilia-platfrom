import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { signInOwner } from './operations-helpers';

test('FNC-DQ-001 centro de calidad sin violaciones WCAG automatizadas', async ({ page }) => {
  await signInOwner(page);
  await page.goto('/calidad');
  await expect(page.getByRole('heading', { level: 1, name: 'Centro de calidad' }))
    .toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
