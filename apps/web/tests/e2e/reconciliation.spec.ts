import { expect, test, type Page } from '@playwright/test';

import { findReviewPair, reviewUrl, signInReviewer } from './reconciliation-helpers';

async function openReconciliation(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);
  await page.getByRole('link', { name: 'Conciliacion' }).click();
  await expect(page).toHaveURL(/\/conciliacion$/);
}

test('FNC-REC-001 abre una estacion read-only con estados explicitos', async ({
  page,
}) => {
  await openReconciliation(page);

  await expect(
    page.getByRole('heading', { level: 1, name: 'Conciliacion visual' }),
  ).toBeVisible();
  await expect(page.getByText('Solo candidatos.')).toBeVisible();
  await expect(page.getByLabel('Dataset izquierdo')).toBeVisible();
  await expect(page.getByLabel('Dataset derecho')).toBeVisible();
  await expect(page.getByLabel('Ventana maxima entre fechas')).toHaveValue('3');
  await expect(page.getByRole('button', { name: 'Buscar candidatos' })).toBeVisible();
  await expect(
    page.getByRole('button', { name: /confirmar|aprobar|automatic/i }),
  ).toHaveCount(0);

  const left = page.getByLabel('Dataset izquierdo');
  const right = page.getByLabel('Dataset derecho');
  const versions = await left.locator('option').count();
  if (versions < 3) {
    await expect(page.getByText('Se necesitan dos datasets aptos')).toBeVisible();
  } else {
    await left.selectOption({ index: 1 });
    await right.selectOption({ index: 2 });
    await page.getByRole('button', { name: 'Buscar candidatos' }).click();
    await expect(page).toHaveURL(/izquierda=.+&derecha=.+&ventana=3/);
    await expect(
      page.getByText('Los datasets no estan disponibles').or(
        page.getByText('No hay candidatos con estas reglas'),
      ).or(page.getByLabel('Candidatos encontrados')),
    ).toBeVisible();
  }
});

test('FNC-REC-001 conserva un estado invalido en vez de caer en latest', async ({
  page,
}) => {
  await openReconciliation(page);
  const base = page.url();
  await page.goto(`${base}?izquierda=repetido&derecha=repetido&ventana=32`);

  await expect(page.getByText('La comparacion solicitada no es valida')).toBeVisible();
  await expect(page.getByText('Solo candidatos.')).toBeVisible();
});

test('FNC-REC-002 un revisor confirma sin alterar ni certificar saldos', async ({
  page,
  request,
}) => {
  const pair = await findReviewPair(request, 'open');
  await signInReviewer(page);
  await page.goto(reviewUrl(pair));

  const open = page.getByLabel('Estado de revision').filter({
    hasText: 'Pendiente de decision humana',
  }).first();
  await expect(open).toBeVisible();
  await open.getByRole('button', { name: 'Confirmar revision' }).click();

  await expect(page.getByText('Revision confirmada').first()).toBeVisible();
  await expect(page.getByText('Registro humano sin efecto financiero.').first())
    .toBeVisible();
  await expect(page.getByText(/demuestra que los saldos esten conciliados/))
    .toBeVisible();
});
