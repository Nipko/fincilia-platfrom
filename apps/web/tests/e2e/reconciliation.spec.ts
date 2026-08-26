import { expect, test, type Page } from '@playwright/test';

import {
  findGroupComposition,
  findReviewPair,
  groupUrl,
  reviewUrl,
  signInReviewer,
} from './reconciliation-helpers';

async function openReconciliation(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+$/);
  await page.getByRole('link', { name: 'Cruzar movimientos' }).click();
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

test('FNC-REC-002 conserva una decision humana sin alterar ni certificar saldos', async ({
  page,
  request,
}) => {
  const pair = await findReviewPair(request, 'open');
  await signInReviewer(page);
  await page.goto(reviewUrl(pair));

  const review = page.locator(`#revision-${pair.candidateId}`);
  await expect(review).toBeVisible();
  if (pair.status === 'open') {
    if (pair.confirmationConflict) {
      await expect(review.getByText('No se puede confirmar este par')).toBeVisible();
      await expect(review.getByRole('button', { name: 'Confirmar revision' }))
        .toHaveCount(0);
      await review.getByRole('button', { name: 'Rechazar candidato' }).click();
      await expect(review.getByText('Candidato rechazado')).toBeVisible();
    } else {
      await expect(review.getByText('Pendiente de decision humana')).toBeVisible();
      await review.getByRole('button', { name: 'Confirmar revision' }).click();
      await expect(review.getByText('Revision confirmada')).toBeVisible();
    }
  } else {
    await expect(review.getByText(
      pair.status === 'confirmed' ? 'Revision confirmada' : 'Candidato rechazado',
    )).toBeVisible();
    await expect(review.getByRole('button', { name: /Confirmar revision|Rechazar candidato/ }))
      .toHaveCount(0);
  }
  await expect(review.getByText('Registro humano sin efecto financiero.')).toBeVisible();
  await expect(page.getByText(/demuestra que los saldos esten conciliados/))
    .toBeVisible();
});

test('FNC-REC-003 prioriza revisiones multiempresa y abre el expediente exacto', async ({
  page,
}) => {
  await signInReviewer(page);
  await page.getByRole('link', { name: 'Abrir bandeja de revisiones multiempresa' })
    .click();
  await expect(page).toHaveURL(/\/revisiones$/);
  await expect(page.getByRole('heading', { name: 'Bandeja de revisiones' }))
    .toBeVisible();
  await expect(page.getByText(/no prueba saldos/i)).toBeVisible();

  // El caso REC-002 anterior confirma deliberadamente el unico expediente que
  // trae una semilla vacia. La bandeja debe conservarlo en el historico, no
  // fabricar otro pendiente ni depender del orden de ejecucion de la suite.
  await page.getByRole('link', { name: 'Todas' }).click();
  await expect(page).toHaveURL(/\/revisiones\?estado=todas$/);

  const first = page.getByRole('link', { name: 'Abrir expediente' }).first();
  await expect(first).toBeVisible();
  await first.click();
  await expect(page).toHaveURL(/\/conciliacion\?izquierda=.+&derecha=.+#revision-/);
  await expect(page.getByLabel('Estado de revision').first()).toBeVisible();
  await expect(page.getByText(/sin efecto financiero/i).first()).toBeVisible();
});

test('FNC-REC-005 compone un borrador 1:N o N:1 sin ofrecer confirmacion', async ({
  page,
  request,
}) => {
  const composition = await findGroupComposition(request);
  await openReconciliation(page);
  await page.goto(groupUrl(composition));

  const relation = composition.anchorSide === 'left' ? '1:N' : 'N:1';
  const form = page.getByRole('form', { name: `Crear propuesta ${relation}` });
  await expect(form).toBeVisible();
  await form.locator('select[name="anchorMovementId"]')
    .selectOption(composition.anchorMovementId);
  for (const movementId of composition.relatedMovementIds) {
    await form.locator(`input[name="relatedMovementIds"][value="${movementId}"]`)
      .check();
  }
  await form.getByRole('button', { name: `Guardar propuesta ${relation}` }).click();
  await expect(form.getByRole('status')).toContainText(/Borrador|composicion/i);

  const saved = page.getByLabel('Borradores agrupados').locator('article').first();
  await expect(saved).toBeVisible();
  await expect(saved.getByText(/Estado draft: no hay asignaciones/)).toBeVisible();
  await expect(saved.getByRole('button', { name: /confirmar|cerrar/i })).toHaveCount(0);
});
