import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-004 integra statements sin habilitar un cierre', async ({
  page,
}) => {
  await signInOwner(page);
  await page.getByRole('link', { name: 'Abrir preparacion de cierre' }).click();
  await expect(page).toHaveURL(/\/preparacion-cierre$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Preparacion de cierre' }))
    .toBeVisible();
  await expect(page.getByRole('status').filter({
    hasText: 'La operacion de cierre permanece deshabilitada',
  })).toBeVisible();
  await expect(page.getByText(/Evidencia bloqueada|Evidencia lista para revision/).first())
    .toBeVisible();
  await expect(page.getByRole('button', { name: /cerrar|ejecutar cierre/i }))
    .toHaveCount(0);

  await page.getByRole('combobox', { name: 'Empresa' }).selectOption(ESPIGA);
  await page.getByRole('button', { name: 'Actualizar diagnostico' }).click();
  await expect.poll(() => new URL(page.url()).searchParams.get('empresa'))
    .toBe(ESPIGA);
  await expect(page.getByRole('heading', { level: 2, name: 'Panaderia La Espiga SAS' }))
    .toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: 'Transportes Andinos SAS' }))
    .toHaveCount(0);

  await page.getByRole('combobox', { name: 'Periodo' }).selectOption({ index: 1 });
  await page.getByRole('button', { name: 'Actualizar diagnostico' }).click();
  const selectedPeriod = new URL(page.url()).searchParams.get('periodo');
  expect(selectedPeriod).toMatch(/^\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$/);
  await expect(page.getByText(/Evidencia bloqueada|Evidencia lista para revision/))
    .toHaveCount(1);

  await page.getByText('Ver evidencia por fuente', { exact: false }).first().click();
  await expect(page.getByRole('table').first()).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Fuente' }).first()).toBeVisible();
  const balances = page.locator('.close-control').filter({ hasText: 'Saldos por cuenta' }).first();
  await expect(balances).toBeVisible();
  await expect(balances.getByText('Bloquea')).toBeVisible();
  await page.getByText('Ver cobertura por cuenta', { exact: false }).first().click();
  await expect(page.getByRole('columnheader', { name: 'Statement' }).first()).toBeVisible();
  const lineage = page.locator('summary:visible').filter({ hasText: 'Ver trazabilidad' });
  if (await lineage.count()) {
    await lineage.first().click();
    await expect(page.getByText(/Vista solo de identidades, versiones y huellas SHA-256/)
      .first()).toBeVisible();
    await expect(page.locator('.statement-lineage code.digest').first())
      .toHaveText(/^[a-f0-9]{64}$/);
  }
  await expect(page.getByRole('button', { name: /cerrar|certificar|aceptar materialidad/i }))
    .toHaveCount(0);
});
