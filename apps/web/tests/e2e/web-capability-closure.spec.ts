import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-WEB-005 cierra estados web sin simular proveedores', async ({ page }) => {
  await signInOwner(page);

  await page.goto('/cuenta');
  await expect(page.getByRole('heading', { name: 'Planes de Fincilia' })).toBeVisible();
  await expect(page.getByText('Pagos desactivados')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Qué está activo y qué no' }).first())
    .toBeVisible();

  await page.goto(`/recordatorios?empresa=${ESPIGA}`);
  await expect(page.getByRole('heading', { name: 'Avisos por correo' })).toBeVisible();
  await expect(page.getByText('Entrega externa desactivada')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Historial verificable' })).toBeVisible();

  await page.goto('/calidad');
  await page.getByText('Cobertura exacta de las reglas').click();
  await expect(page.getByText('amount_outlier_10x_median')).toBeVisible();
  await expect(page.getByText(/ninguna equivale a una acusación/i)).toBeVisible();

  await page.goto(`/empresas/${ESPIGA}/documentos`);
  await expect(page.getByRole('heading', { name: 'Formatos y tratamiento' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'CSV' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'PDF' })).toBeVisible();
  await expect(page.getByText(/OCR todavía no transmite documentos/i)).toBeVisible();
});
