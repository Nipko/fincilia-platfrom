import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import {
  findPublishedDataset,
  publishedDatasetUrl,
  signInReviewer,
} from './reconciliation-helpers';

test('FNC-EXP-001 no introduce violaciones axe en la salida limpia', async ({
  page,
  request,
}) => {
  const dataset = await findPublishedDataset(request);
  await signInReviewer(page);
  await page.goto(publishedDatasetUrl(dataset));
  await expect(page.getByRole('link', { name: 'Descargar CSV canonico' })).toBeVisible();

  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();

  expect(result.violations).toEqual([]);
});
