import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const API_BASE = process.env.FINCILIA_E2E_API_URL ?? 'http://127.0.0.1:58080';
const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';

async function apiSession(request: APIRequestContext, username: string): Promise<string> {
  const response = await request.post(`${API_BASE}/api/v1/auth/session`, {
    data: { username, secret: 'fincilia-demo-only' },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).token as string;
}

async function removeSyntheticReadOnly(request: APIRequestContext): Promise<void> {
  const token = await apiSession(request, 'sofia@demo.local');
  const members = await request.get(`${API_BASE}/api/v1/companies/${ESPIGA}/members`, {
    headers: { authorization: `Bearer ${token}` },
  });
  expect(members.ok()).toBeTruthy();
  const carla = (await members.json() as Array<{
    subject_id: string;
    display_name: string;
    company_roles: string[];
  }>).find((member) => member.display_name === 'Carla Auditora');
  expect(carla).toBeTruthy();
  if (carla!.company_roles.includes('read_only')) {
    const response = await request.delete(
      `${API_BASE}/api/v1/companies/${ESPIGA}/members/${carla!.subject_id}/roles`,
      {
        headers: { authorization: `Bearer ${token}` },
        data: { role: 'read_only', reason_code: 'access_removed' },
      },
    );
    expect(response.ok()).toBeTruthy();
  }
}

async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

test.beforeEach(async ({ request }) => {
  await removeSyntheticReadOnly(request);
});

test.afterEach(async ({ request }) => {
  await removeSyntheticReadOnly(request);
});

test('owner asigna y revoca un rol sin perder su sesion', async ({ page }) => {
  await signIn(page, 'sofia@demo.local');
  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await page.getByRole('link', { name: 'Equipo y roles' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Equipo y roles' }))
    .toBeVisible();

  const carla = page.locator('article').filter({ hasText: 'Carla Auditora' });
  await expect(carla).toContainText('Sin acceso a esta empresa');
  await carla.getByLabel('Nuevo rol para Carla Auditora').selectOption('read_only');
  await carla.getByRole('button', { name: 'Asignar rol' }).click();

  await expect(carla.getByText('Solo lectura', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/empresas/${ESPIGA}/equipo$`));
  await expect(page.getByRole('link', { name: 'Volver a la empresa' })).toBeVisible();

  await carla.getByText('Revocar un rol activo').click();
  await carla.getByLabel(/Motivo para revocar Solo lectura/)
    .selectOption('access_removed');
  await carla.getByRole('button', { name: 'Revocar Solo lectura' }).click();

  await expect(carla.getByText('Sin acceso a esta empresa')).toBeVisible();
});

test('reviewer no ve ni abre la administracion del equipo', async ({ page }) => {
  await signIn(page, 'beto@demo.local');
  await page.getByRole('link', { name: 'Abrir Panaderia La Espiga SAS' }).click();
  await expect(page.getByRole('link', { name: 'Equipo y roles' })).toHaveCount(0);

  await page.goto(`/empresas/${ESPIGA}/equipo`);
  await expect(page.getByRole('heading', { name: 'Equipo no disponible' })).toBeVisible();
  await expect(page.getByText('Carla Auditora')).toHaveCount(0);
});
