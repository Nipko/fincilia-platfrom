import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-RPT-001 muestra historicos por empresa y exporta la serie exacta', async ({
  page,
}) => {
  test.setTimeout(60_000);
  await signInOwner(page);
  await page.getByRole('link', { name: 'Abrir informes e historicos' }).click();
  await expect(page).toHaveURL(/\/informes/);
  await expect(page.getByRole('heading', { level: 1, name: 'Informes e historicos' }))
    .toBeVisible();
  await expect(page.getByText(/Los importes permanecen separados por empresa/))
    .toBeVisible();
  await expect(page.getByRole('heading', { name: 'Panaderia La Espiga SAS' }))
    .toBeVisible();
  await expect(page.getByRole('heading', { name: 'Transportes Andinos SAS' }))
    .toBeVisible();

  await page.locator('select[name="empresa"]').selectOption(ESPIGA);
  await page.locator('select[name="dias"]').selectOption('365');
  await page.getByRole('button', { name: 'Actualizar' }).click();
  await expect(page).toHaveURL(new RegExp(`empresa=${ESPIGA}.*dias=365`));
  await expect(page.getByRole('heading', { name: 'Panaderia La Espiga SAS' }))
    .toBeVisible();
  await expect(page.getByRole('heading', { name: 'Transportes Andinos SAS' }))
    .toHaveCount(0);
  await expect(page.getByRole('img', { name: /Actividad mensual de Panaderia/ }))
    .toBeVisible();

  const downloadLink = page.getByRole('link', { name: 'Descargar CSV' });
  const href = await downloadLink.getAttribute('href');
  expect(href).toBeTruthy();
  const response = await page.request.get(href!);
  expect(response.status()).toBe(200);
  expect(response.headers()['content-disposition']).toMatch(
    /^attachment; filename="fincilia-informe-\d{4}-\d{2}-\d{2}-365d\.csv"$/,
  );
  const csv = await response.text();
  expect(csv).toContain('month,currency,movement_count,inflow_amount,outflow_amount');
  expect(csv).not.toContain('Panaderia La Espiga');
});
