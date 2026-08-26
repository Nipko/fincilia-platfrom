import { expect, test } from '@playwright/test';

import { findPublishedDataset } from './reconciliation-helpers';
import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-002 observa un saldo desde celdas publicadas sin habilitar cierre', async ({
  page,
  request,
}) => {
  await findPublishedDataset(request);
  await signInOwner(page);
  await page.goto(`/empresas/${ESPIGA}/saldos`);

  await expect(page.getByRole('heading', { level: 1, name: 'Saldos por cuenta' }))
    .toBeVisible();
  await expect(page.getByRole('status').filter({
    hasText: 'Estos saldos aun no son entrada de cierre',
  })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Fila de evidencia' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Columna del importe' }))
    .not.toHaveValue('');
  await expect(page.getByRole('combobox', { name: 'Columna de la fecha del saldo' }))
    .not.toHaveValue('');

  await page.getByRole('button', { name: 'Registrar observacion de saldo' }).click();
  await expect(page.getByRole('status').filter({
    hasText: /Saldo observado|misma observacion ya estaba registrada/,
  })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Historico inmutable' })).toBeVisible();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByText('Pendiente').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /cerrar|ejecutar cierre/i })).toHaveCount(0);
});
