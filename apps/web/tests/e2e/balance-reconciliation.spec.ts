import { expect, test } from '@playwright/test';

import { findPublishedDataset } from './reconciliation-helpers';
import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-003 presenta la estacion versionada sin ejecutar cierre', async ({
  page,
  request,
}) => {
  await findPublishedDataset(request);
  await signInOwner(page);
  await page.goto(`/empresas/${ESPIGA}/conciliacion-saldos`);

  await expect(page.getByRole('heading', { level: 1, name: 'Conciliacion de saldos' }))
    .toBeVisible();
  await expect(page.getByRole('status').filter({
    hasText: 'Una diferencia explicada no es un cierre certificado',
  })).toBeVisible();
  await expect(page.getByText('Fuentes esperadas')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Completitud por fuente y periodo' }))
    .toBeVisible();
  await expect(page.getByRole('heading', { name: 'Calcular estado' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Estados calculados' })).toBeVisible();
  await expect(page.getByRole('button', { name: /cerrar|certificar|publicar asiento/i }))
    .toHaveCount(0);
});
