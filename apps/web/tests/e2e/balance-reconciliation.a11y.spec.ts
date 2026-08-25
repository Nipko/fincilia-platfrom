import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { findPublishedDataset } from './reconciliation-helpers';
import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-003 estacion de conciliacion de saldos cumple Axe', async ({
  page,
  request,
}) => {
  await findPublishedDataset(request);
  await signInOwner(page);
  await page.goto(`/empresas/${ESPIGA}/conciliacion-saldos`);
  await expect(page.getByRole('heading', { level: 1, name: 'Conciliacion de saldos' }))
    .toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
