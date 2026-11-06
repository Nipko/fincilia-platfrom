import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

// FNC-SMB-004 · axe sobre el alta con perfil, el modo simple y los ajustes.
const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';

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
    .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map((node) => node.target),
    }));

  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

test('TST-A11Y-SMB: alta con pregunta de equipo sin hallazgos serios', async ({ page }) => {
  await signIn(page, 'sofia@demo.local');
  await page.goto('/empresas/nueva');
  await expect(page.getByRole('radio', { name: /1–2 personas/ })).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-SMB: inicio en modo simple sin hallazgos serios', async ({ page }) => {
  await signIn(page, 'sofia@demo.local');
  const marker = `${Date.now()}-${test.info().retry}`;
  await page.goto('/empresas/nueva');
  await page.getByLabel('Razon social').fill(`Pyme A11y ${marker}`);
  await page.getByLabel('Identificacion tributaria sintetica').fill(`SYN-A11Y-${marker}`);
  await page.getByRole('radio', { name: /1–2 personas/ }).check();
  await page.getByLabel('Identificador sintetico de cuenta').fill(`SYN-A11Y-ACC-${marker}`);
  await page.getByRole('button', { name: 'Crear empresa y continuar' }).click();
  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/fuentes\?alta=creada$/);
  const companyId = /\/empresas\/([0-9a-f-]+)\/fuentes/.exec(page.url())![1]!;

  await page.goto(`/empresas/${companyId}`);
  await expect(page.getByRole('list', { name: 'Pasos del modo simple' })).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-SMB: ajustes de perfil sin hallazgos serios', async ({ page }) => {
  await signIn(page, 'sofia@demo.local');
  await page.goto(`/empresas/${ESPIGA}/ajustes`);
  await expect(page.getByRole('heading', { level: 2, name: 'Perfil operativo' })).toBeVisible();
  await expectNoSeriousOrCriticalViolations(page);
});
