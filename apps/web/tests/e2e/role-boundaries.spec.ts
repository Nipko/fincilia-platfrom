import { expect, test, type Page } from '@playwright/test';

const TRANSPORTES_ID = 'ba382f36-c2b3-55c8-9d85-4bdc74979d19';

async function signIn(
  page: Page,
  username: 'ana@demo.local' | 'beto@demo.local',
): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
  await expect(
    page.getByRole('heading', { level: 1, name: 'Portafolio de empresas' }),
  ).toBeVisible();
}

test('Ana ve solamente sus dos empresas y capacidades de preparacion', async ({
  page,
}) => {
  await signIn(page, 'ana@demo.local');

  const companies = page.locator('ul.companies > li');
  await expect(companies).toHaveCount(2);
  await expect(page.getByText('Panaderia La Espiga SAS', { exact: true })).toBeVisible();
  await expect(page.getByText('Transportes Andinos SAS', { exact: true })).toBeVisible();
  await expect(page.getByText('Banco de Pruebas Uno SAS', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Banco de Pruebas Dos SAS', { exact: true })).toHaveCount(0);

  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Panaderia La Espiga SAS',
  );
  await expect(page.getByText('preparer', { exact: true })).toBeVisible();
  await expect(page.getByText('dataset.map', { exact: true })).toBeVisible();
  await expect(page.getByText('dataset.publish', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Extracto o soporte')).toBeVisible();
});

test('Beto ve una empresa, capacidades de revision y ninguna carga', async ({
  page,
}) => {
  await signIn(page, 'beto@demo.local');

  const companies = page.locator('ul.companies > li');
  await expect(companies).toHaveCount(1);
  await expect(page.getByText('Panaderia La Espiga SAS', { exact: true })).toBeVisible();
  await expect(page.getByText('Transportes Andinos SAS', { exact: true })).toHaveCount(0);

  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await expect(page.getByText('reviewer', { exact: true })).toBeVisible();
  await expect(page.getByText('dataset.publish', { exact: true })).toBeVisible();
  await expect(page.getByText('dataset.map', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('Extracto o soporte')).toHaveCount(0);
});

test('una URL directa no revela a Beto una empresa ajena', async ({ page }) => {
  await signIn(page, 'beto@demo.local');

  await page.goto(`/empresas/${TRANSPORTES_ID}`);

  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    /^(Sin acceso|No encontramos esta pagina|No encontramos esta página)$/,
  );
  await expect(page.getByText('Transportes Andinos SAS', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Panaderia La Espiga SAS', { exact: true })).toHaveCount(0);
});
