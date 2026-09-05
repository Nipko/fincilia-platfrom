import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

import { signInOwner } from './operations-helpers';
import { syntheticScannedPdf } from './pdf-ocr-helper';

test('PDF imagen recorre OCR local, perfil y linaje sin proveedor externo', async ({ page }) => {
  test.setTimeout(120_000);
  const marker = Date.now().toString(36);
  await signInOwner(page);
  const company = page.getByRole('link', { name: /Panaderia La Espiga SAS/ });
  await company.click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);
  const source = page.getByLabel('Fuente del documento');
  const sourceId = await source.locator('option').filter({
    hasText: 'Extracto bancario (demo)',
  }).getAttribute('value');
  expect(sourceId).toMatch(/^[0-9a-f-]+$/);
  await source.selectOption(sourceId!);

  await page.getByLabel('Extracto o soporte').setInputFiles({
    name: `ocr-local-sintetico-${marker}.pdf`,
    mimeType: 'application/pdf',
    buffer: syntheticScannedPdf(marker),
  });
  await page.getByRole('button', { name: 'Subir' }).click();
  await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);

  await expect.poll(async () => {
    await page.reload({ waitUntil: 'domcontentloaded' });
    return page.getByRole('rowheader', { name: 'Texto OCR', exact: true }).count();
  }, { timeout: 90_000, intervals: [1_000, 1_500, 2_000] }).toBe(1);
  await expect(page.getByText('OCR local completado')).toBeVisible();
  await expect(page.getByText(/sin transmisión externa/i)).toBeVisible();
  await expect(page.getByText(/motor tesseract-5\.5\.1\/pdfium-5\.13\.0/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Mapear y publicar' })).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
