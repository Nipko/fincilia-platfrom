import { expect, test, type Page } from '@playwright/test';

const COMPANY_ID = '161b0037-c445-50aa-b400-72632d3f53f0';

async function signIn(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

async function expectNoPageOverflow(page: Page): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test.describe('FNC-IAM-002 · centro de identidad', () => {
  test('expone sesion, alcance y responsabilidades sin datos del IdP', async ({
    page,
  }) => {
    await signIn(page);
    await page.goto('/cuenta');

    await expect(page.getByRole('heading', { level: 1, name: 'Tu cuenta' }))
      .toBeVisible();
    await expect(page.getByText('Cuenta local de demostración')).toBeVisible();
    await expect(page.getByText('Modo sintético')).toBeVisible();
    await expect(page.getByText('Sesión actual')).toBeVisible();
    await expect(page.getByText('Panaderia La Espiga SAS')).toBeVisible();
    await expect(page.getByText('La identidad no concede acceso financiero'))
      .toBeVisible();
    await expect(page.getByText('ana@demo.local')).toHaveCount(0);
  });
});

test.describe('FNC-ACC-001 · recorrido contable', () => {
  test('presenta las siete etapas y conserva el limite previo al cierre', async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(`/empresas/${COMPANY_ID}/flujo-contable`);

    await expect(page.getByRole('heading', { level: 1, name: 'Flujo contable' }))
      .toBeVisible();
    await expect(page.getByRole('list', { name: 'Etapas del flujo contable' }))
      .toBeVisible();
    await expect(page.locator('.flow-stage')).toHaveCount(7);
    await expect(page.getByRole('heading', { level: 2, name: 'Configurar cuentas y fuentes' }))
      .toBeVisible();
    await expect(page.getByRole('heading', { level: 2, name: 'Preparar expediente de cierre' }))
      .toBeVisible();
    await expect(
      page.getByRole('heading', {
        level: 2,
        name: 'Preparación completa no significa cierre certificado',
      }),
    ).toBeVisible();
  });
});

test.describe('FNC-UX-003 · experiencia premium responsive', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('cuenta y flujo contable no producen overflow global', async ({ page }) => {
    await signIn(page);

    await page.goto('/cuenta');
    await expect(page.getByRole('navigation', { name: 'Navegacion principal' }))
      .toBeVisible();
    await expectNoPageOverflow(page);

    await page.goto(`/empresas/${COMPANY_ID}/flujo-contable`);
    await expect(page.getByRole('heading', { level: 1, name: 'Flujo contable' }))
      .toBeVisible();
    await expectNoPageOverflow(page);
  });
});
