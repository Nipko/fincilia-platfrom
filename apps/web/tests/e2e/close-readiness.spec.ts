import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

test('FNC-CLS-001 diagnostica por periodo sin habilitar un cierre', async ({
  page,
}) => {
  await signInOwner(page);
  await page.getByRole('link', { name: 'Abrir preparacion de cierre' }).click();
  await expect(page).toHaveURL(/\/preparacion-cierre$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Preparacion de cierre' }))
    .toBeVisible();
  await expect(page.getByRole('status').filter({
    hasText: 'Todos los periodos permanecen bloqueados',
  })).toBeVisible();
  await expect(page.getByText('No listo para cierre').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /cerrar|ejecutar cierre/i }))
    .toHaveCount(0);

  await page.getByRole('combobox', { name: 'Empresa' }).selectOption(ESPIGA);
  await page.getByRole('button', { name: 'Actualizar diagnostico' }).click();
  await expect(page).toHaveURL(new RegExp(`empresa=${ESPIGA}$`));
  await expect(page.getByRole('heading', { level: 2, name: 'Panaderia La Espiga SAS' }))
    .toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: 'Transportes Andinos SAS' }))
    .toHaveCount(0);

  await page.getByText('Ver evidencia por fuente', { exact: false }).first().click();
  await expect(page.getByRole('table').first()).toBeVisible();
  await expect(page.getByRole('columnheader', { name: 'Fuente' }).first()).toBeVisible();
  await expect(page.getByText('Saldos por cuenta').first()).toBeVisible();
  await expect(page.getByText('Aun no disponible').first()).toBeVisible();
});
