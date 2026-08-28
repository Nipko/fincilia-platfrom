import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

async function expectNoSeriousOrCriticalViolations(page: Page): Promise<void> {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
    .analyze();
  const blocking = result.violations
    .filter(
      (violation) =>
        violation.impact === 'serious' || violation.impact === 'critical',
    )
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map((node) => node.target),
    }));

  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

test('TST-A11Y-001: ingreso publico sin hallazgos serios o criticos', async ({
  page,
}) => {
  await page.goto('/entrar');

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-REG-005: registro publico sintetico sin hallazgos serios o criticos', async ({
  page,
}) => {
  await page.goto('/registro');

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: no encontrado conserva la misma base accesible', async ({
  page,
}) => {
  await page.goto('/ruta-sintetica-inexistente');

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: portafolio autenticado de preparador', async ({ page }) => {
  await signIn(page, 'ana@demo.local');

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: alta completa de empresa para owner', async ({ page }) => {
  await signIn(page, 'sofia@demo.local');
  await page.getByRole('link', { name: 'Crear una empresa' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Nueva empresa' }))
    .toBeVisible();

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: estacion de conciliacion sintetica', async ({ page }) => {
  await signIn(page, 'ana@demo.local');
  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await page.getByRole('link', { name: 'Cruzar movimientos' }).click();
  await expect(
    page.getByRole('heading', { level: 1, name: 'Conciliacion visual' }),
  ).toBeVisible();

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: denegacion cross-company de revisor', async ({ page }) => {
  await signIn(page, 'beto@demo.local');
  await page.goto('/empresas/ba382f36-c2b3-55c8-9d85-4bdc74979d19');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

  await expectNoSeriousOrCriticalViolations(page);
});
