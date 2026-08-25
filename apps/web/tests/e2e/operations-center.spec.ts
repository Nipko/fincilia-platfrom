import { expect, test } from '@playwright/test';

import {
  ESPIGA,
  ensureSyntheticReminder,
  signInOwner,
  signInReviewer,
} from './operations-helpers';

test('FNC-OPS-001 muestra el recordatorio sintetico y conserva filtros', async ({
  page,
  request,
}) => {
  const fixture = await ensureSyntheticReminder(request);
  await signInOwner(page);
  await page.getByRole('link', { name: 'Abrir ciclos y recordatorios' }).click();
  await expect(page).toHaveURL(/\/recordatorios/);
  await expect(page.getByRole('heading', {
    level: 1, name: 'Centro de ciclos y recordatorios',
  })).toBeVisible();
  await expect(page.getByRole('heading', { name: fixture.sourceName })).toBeVisible();
  await expect(page.getByText('Ana Preparadora')).toBeVisible();
  await expect(page.getByText(
    `Evaluado al ${fixture.localDate} en America/Bogota.`,
  )).toBeVisible();
  await expect(page.getByText(/no prueban que se envio correo/i)).toBeVisible();

  await page.getByLabel('Empresa').selectOption(ESPIGA);
  await page.getByRole('button', { name: 'Aplicar' }).click();
  await expect(page).toHaveURL(new RegExp(`empresa=${ESPIGA}`));
  await page.getByRole('link', { name: 'Todo el historico' }).click();
  await expect(page).toHaveURL(/estado=todos/);
  await expect(page).toHaveURL(new RegExp(`empresa=${ESPIGA}`));
  await expect(page.getByRole('link', { name: 'Abrir fuente' })).toHaveAttribute(
    'href', `/empresas/${ESPIGA}/fuentes/${fixture.sourceId}#ciclo-esperado`,
  );
});

test('FNC-OPS-001 no presenta permiso ausente como cero periodos', async ({ page }) => {
  await signInReviewer(page);
  await page.goto('/recordatorios');
  await expect(page.getByText('Vista parcial.')).toBeVisible();
  await expect(page.getByText(/no se contabilizan como cero pendientes/i))
    .toBeVisible();
  await expect(page.getByText(/un vacio operativo no certifica/i)).toBeVisible();
});
