import { expect, test, type Page } from '@playwright/test';

async function expectNoPageOverflow(page: Page): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test.describe('FNC-WEB-004 · shell visual responsive', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test('acceso, portafolio y empresa conservan jerarquia sin overflow global', async ({
    page,
  }) => {
    await page.goto('/entrar');

    await expect(page.getByLabel('Fincilia, ir al portafolio')).toBeVisible();
    await expect(page.getByRole('heading', { level: 1, name: 'Fincilia' })).toBeVisible();
    await expectNoPageOverflow(page);

    await page.getByLabel('Usuario').fill('ana@demo.local');
    await page.getByLabel('Contrasena').fill('fincilia-demo-only');
    await page.getByRole('button', { name: 'Entrar' }).click();

    await expect(page).toHaveURL(/\/empresas$/);
    await expect(
      page.getByRole('navigation', { name: 'Navegacion principal' }),
    ).toBeVisible();
    await expect(
      page.getByRole('navigation', { name: 'Herramientas multiempresa' }),
    ).toBeVisible();
    await expectNoPageOverflow(page);

    await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      'Panaderia La Espiga SAS',
    );
    await expect(
      page.getByRole('navigation', { name: 'Navegacion de la empresa' }),
    ).toBeVisible();
    await expect(page.getByText('Acceso de esta cuenta')).toBeVisible();
    await expectNoPageOverflow(page);
  });
});
