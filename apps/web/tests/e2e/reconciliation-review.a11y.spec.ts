import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { findReviewPair, reviewUrl, signInReviewer } from './reconciliation-helpers';

test('FNC-REC-002 no introduce violaciones axe en el expediente', async ({ page, request }) => {
  const pair = await findReviewPair(request);
  await signInReviewer(page);
  await page.goto(reviewUrl(pair));
  await expect(page.getByLabel('Estado de revision').first()).toBeVisible();

  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();

  expect(result.violations).toEqual([]);
});
