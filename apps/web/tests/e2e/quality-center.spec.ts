import { expect, test } from '@playwright/test';

import { ESPIGA, signInOwner } from './operations-helpers';

async function signInAuditor(page: Parameters<typeof signInOwner>[0]): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('carla@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

test('FNC-DQ-001 evalua y explica calidad sin afirmar fraude', async ({ page }) => {
  await signInOwner(page);
  await page.getByRole('link', { name: 'Abrir centro de calidad' }).click();
  await expect(page).toHaveURL(/\/calidad/);
  await expect(page.getByRole('heading', { level: 1, name: 'Centro de calidad' }))
    .toBeVisible();
  await expect(page.getByText(/no son prueba de fraude/i)).toBeVisible();

  await page.getByLabel('Empresa', { exact: true }).selectOption(ESPIGA);
  await page.getByRole('button', { name: 'Aplicar' }).click();
  await expect(page).toHaveURL(new RegExp(`empresa=${ESPIGA}`));
  await page.getByRole('button', { name: 'Evaluar ahora' }).click();
  await expect(page.getByRole('status').filter({ hasText: /Evaluacion completa|ventana segura/ }))
    .toBeVisible();
  await expect(page.getByText(/^\d+ senales visibles$/i)).toBeVisible();
});

test('FNC-DQ-001 auditor ve senales pero no obtiene gestion', async ({ page }) => {
  await signInAuditor(page);
  await page.goto('/calidad');
  await expect(page.getByText('Solo lectura')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Evaluar ahora' })).toHaveCount(0);
});
