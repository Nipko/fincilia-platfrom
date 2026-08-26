import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { findPublishedDataset } from './reconciliation-helpers';
import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-002 estacion de saldos no introduce violaciones WCAG automatizadas', async ({
  page,
  request,
}) => {
  await findPublishedDataset(request);
  await signInOwner(page);
  await page.goto(`/empresas/${ESPIGA}/saldos`);
  await expect(page.getByRole('heading', { level: 1, name: 'Saldos por cuenta' }))
    .toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});
