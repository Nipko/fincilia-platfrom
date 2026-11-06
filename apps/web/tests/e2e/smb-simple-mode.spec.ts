import { expect, test, type Page } from '@playwright/test';

// FNC-SMB-004 · modo pyme (ADR-039). Datos exclusivamente sinteticos.
const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';

async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

async function createCompany(page: Page, band: RegExp): Promise<string> {
  const marker = `${Date.now()}-${test.info().retry}`;
  await page.goto('/empresas/nueva');
  await expect(page.getByRole('heading', { level: 1, name: 'Nueva empresa' })).toBeVisible();
  await expect(page.getByRole('group', {
    name: '¿Cuántas personas revisan las finanzas de la empresa?',
  })).toBeVisible();
  await page.getByLabel('Razon social').fill(`Pyme Sintetica E2E ${marker}`);
  await page.getByLabel('Identificacion tributaria sintetica').fill(`SYN-SMB-${marker}`);
  await page.getByRole('radio', { name: band }).check();
  await page.getByLabel('Identificador sintetico de cuenta').fill(`SYN-SMB-ACCOUNT-${marker}`);
  await page.getByRole('button', { name: 'Crear empresa y continuar' }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/fuentes\?alta=creada$/);
  const match = /\/empresas\/([0-9a-f-]+)\/fuentes/.exec(page.url());
  expect(match).toBeTruthy();
  return match![1]!;
}

test.describe('FNC-SMB-004 · modo simple para pymes', () => {
  test('una empresa de 1–2 personas abre en tres pasos con modo contador accesible', async ({
    page,
  }) => {
    await signIn(page, 'sofia@demo.local');
    const companyId = await createCompany(page, /1–2 personas/);

    await page.goto(`/empresas/${companyId}`);
    await expect(page.getByRole('list', { name: 'Pasos del modo simple' })).toBeVisible();
    await expect(page.getByRole('heading', { level: 3, name: 'Subir' })).toBeVisible();
    await expect(page.getByRole('heading', { level: 3, name: 'Revisar pendientes' }))
      .toBeVisible();
    await expect(page.getByRole('heading', { level: 3, name: 'Listo' })).toBeVisible();
    await expect(page.getByText('Perfil Simple')).toBeVisible();

    await page.getByRole('link', { name: 'Modo contador →' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Flujo contable' })).toBeVisible();
    await expect(page.locator('.flow-stage')).toHaveCount(7);
  });

  test('una empresa estricta conserva el flujo de siete etapas', async ({ page }) => {
    await signIn(page, 'ana@demo.local');
    await page.goto(`/empresas/${ESPIGA}`);

    await expect(page.getByRole('list', { name: 'Pasos del modo simple' })).toHaveCount(0);
    await expect(page.getByRole('heading', {
      level: 2, name: 'Flujo contable en siete etapas',
    })).toBeVisible();
    await page.getByRole('link', { name: 'Abrir flujo contable →' }).click();
    await expect(page.locator('.flow-stage')).toHaveCount(7);
  });
});

test.describe('FNC-SMB-004 · perfil operativo', () => {
  test('el owner puede cambiar el perfil con motivo y ve el historial', async ({ page }) => {
    await signIn(page, 'sofia@demo.local');
    const companyId = await createCompany(page, /1–2 personas/);

    await page.goto(`/empresas/${companyId}/ajustes`);
    await expect(page.getByRole('heading', { level: 2, name: 'Perfil operativo' }))
      .toBeVisible();
    await page.getByRole('radio', { name: /Estricto/ }).check();
    await page.getByLabel('Motivo del cambio').fill('Se suma una tercera persona al equipo.');
    await page.getByRole('button', { name: 'Guardar perfil' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Perfil cambiado a Estricto' }))
      .toBeVisible();

    await page.reload();
    await expect(page.getByRole('list', { name: 'Historial del perfil operativo' }))
      .toContainText('Simple → Estricto');
  });

  test('quien no es owner ve el perfil solo para consulta', async ({ page }) => {
    await signIn(page, 'ana@demo.local');
    await page.goto(`/empresas/${ESPIGA}/ajustes`);

    await expect(page.getByRole('heading', { level: 2, name: 'Perfil operativo' }))
      .toBeVisible();
    await expect(page.getByText('Solo el dueño de la empresa puede cambiar el perfil.'))
      .toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar perfil' })).toHaveCount(0);
    await expect(page.getByLabel('Motivo del cambio')).toHaveCount(0);
  });
});
