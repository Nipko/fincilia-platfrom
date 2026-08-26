import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import {
  findGroupComposition,
  findReviewPair,
  groupUrl,
  reviewUrl,
  signInReviewer,
} from './reconciliation-helpers';

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

test('FNC-REC-003 no introduce violaciones axe en la bandeja multiempresa', async ({ page }) => {
  await signInReviewer(page);
  await page.goto('/revisiones');
  await expect(page.getByRole('heading', { name: 'Bandeja de revisiones' }))
    .toBeVisible();

  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();

  expect(result.violations).toEqual([]);
});

test('FNC-REC-005 no introduce violaciones axe en el compositor agrupado', async ({
  page,
  request,
}) => {
  const composition = await findGroupComposition(request);
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
  await page.goto(groupUrl(composition));
  await expect(page.getByRole('heading', {
    name: 'Propuestas agrupadas 1:N y N:1',
  })).toBeVisible();

  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(result.violations).toEqual([]);
});
