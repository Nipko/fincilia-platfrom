import { expect, test, type Page } from '@playwright/test';

async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

test('owner crea empresa, cuenta, fuente y ciclo y entra al espacio nuevo', async ({
  page,
}) => {
  const marker = `${Date.now()}-${test.info().retry}`;
  const legalName = `Empresa Sintetica E2E ${marker}`;

  await signIn(page, 'sofia@demo.local');
  await page.getByRole('link', { name: 'Crear una empresa' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Nueva empresa' }))
    .toBeVisible();

  await page.getByLabel('Razon social').fill(legalName);
  await page.getByLabel('Identificacion tributaria sintetica')
    .fill(`SYN-TAX-${marker}`);
  await page.getByLabel('Nombre visible de la cuenta')
    .fill('Cuenta inicial E2E');
  await page.getByLabel('Identificador sintetico de cuenta')
    .fill(`SYN-ACCOUNT-${marker}`);
  await page.getByLabel('Nombre visible de la fuente')
    .fill('Fuente inicial E2E');
  await page.getByRole('button', { name: 'Crear empresa y continuar' }).click();

  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/fuentes\?alta=creada$/);
  await expect(page.getByRole('status').filter({ hasText: 'Empresa creada' }))
    .toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Fuentes y cuentas' }))
    .toBeVisible();
  await expect(page.getByRole('row', { name: /Cuenta inicial E2E/ })).toBeVisible();
  await expect(page.getByRole('rowheader', { name: 'Fuente inicial E2E' }))
    .toBeVisible();

  await page.getByRole('link', { name: 'Empresas' }).click();
  await expect(page.getByRole('link', { name: `Abrir ${legalName}` })).toBeVisible();
});

test('un miembro sin permiso no ve ni puede abrir el alta', async ({ page }) => {
  await signIn(page, 'ana@demo.local');
  await expect(page.getByRole('link', { name: 'Crear una empresa' })).toHaveCount(0);

  await page.goto('/empresas/nueva');
  await expect(page.getByRole('heading', { level: 2, name: 'No puedes crear empresas' }))
    .toBeVisible();
  await expect(page.getByLabel('Identificacion tributaria sintetica')).toHaveCount(0);
});
