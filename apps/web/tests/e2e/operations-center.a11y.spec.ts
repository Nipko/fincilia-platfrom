import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { ensureSyntheticReminder, signInOwner } from './operations-helpers';

test('FNC-OPS-001 no introduce violaciones Axe en el centro operativo', async ({
  page,
  request,
}) => {
  await ensureSyntheticReminder(request);
  await signInOwner(page);
  await page.goto('/recordatorios');
  await expect(page.getByRole('heading', {
    level: 1, name: 'Centro de ciclos y recordatorios',
  })).toBeVisible();

  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(result.violations).toEqual([]);
});
