import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

import { waitForRenderedText } from './xlsx-helper';

// FNC-SMB-003/004/006 · bandeja pyme, reglas aprobadas y plantillas (ADR-039).
// Datos exclusivamente sinteticos: el par «factura uno/dos/tres» lo crea
// `infra/local/scripts/e2e_fixture.py` en ESPIGA. La suite es serial
// (workers: 1); ESPIGA pasa a `simple` por la API y vuelve a `estricto` al final.
const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';
const API_URL = process.env.FINCILIA_E2E_API_URL ?? 'http://127.0.0.1:58080';
const REASON = 'Prueba E2E sintetica del modo pyme FNC-SMB-004';

async function signIn(page: Page, username: string): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

async function setProfile(request: APIRequestContext, profile: 'simple' | 'estricto') {
  const signed = await request.post(`${API_URL}/api/v1/auth/session`, {
    data: { username: 'sofia@demo.local', secret: 'fincilia-demo-only' },
  });
  expect(signed.ok()).toBeTruthy();
  const token = (await signed.json()).token as string;
  const changed = await request.put(
    `${API_URL}/api/v1/companies/${ESPIGA}/operating-profile`,
    {
      headers: { authorization: `Bearer ${token}` },
      data: { operating_profile: profile, reason: REASON },
    },
  );
  expect(changed.ok(), await changed.text()).toBeTruthy();
}

function bancolombiaCsv(marker: string): Buffer {
  return Buffer.from(
    'Fecha;Descripcion;Sucursal;Documento;Valor;Saldo\n'
    + `13/02/2026;Pago proveedor SYN ${marker};Centro SYN;SYN-0001;-1.234,56;10.000,00\n`
    + '14/02/2026;Abono cliente SYN;Centro SYN;SYN-0002;2.500,00;12.500,00\n',
    'utf8',
  );
}

test.describe('FNC-SMB-002/004 · plantilla despues de subir', () => {
  test('subir un extracto conocido ofrece la plantilla de prueba', async ({ page }) => {
    test.setTimeout(120_000);
    const marker = `${Date.now().toString(36)}-${test.info().retry}`;
    const filename = `bancolombia-${marker}.csv`;
    await signIn(page, 'ana@demo.local');
    await page.goto(`/empresas/${ESPIGA}`);

    const source = page.getByLabel('Fuente del documento');
    const option = source.locator('option').filter({ hasText: 'Extracto bancario (demo)' });
    await expect(option).toHaveCount(1);
    await source.selectOption((await option.getAttribute('value'))!);
    await page.getByLabel('Extracto o soporte').setInputFiles({
      name: filename, mimeType: 'text/csv', buffer: bancolombiaCsv(marker),
    });
    await page.getByRole('button', { name: 'Subir' }).click();
    await expect(page).toHaveURL(/\/documentos\/[0-9a-f-]+\?fuente=[0-9a-f-]+$/);

    // El worker procesa en segundo plano: se recarga hasta ver la oferta.
    await waitForRenderedText(page, filename, 'Usar plantilla Bancolombia', 90_000);
    const offer = page.getByRole('region', { name: 'Columnas del archivo' });
    await expect(offer.getByText('Plantilla de prueba — verifica las columnas')).toBeVisible();
    await expect(offer.getByRole('link', { name: 'Prefiero mapear a mano' })).toBeVisible();
    await offer.getByRole('button', { name: 'Usar plantilla Bancolombia' }).click();
    await expect(page).toHaveURL(/\/mapeo\?mapeo=[0-9a-f-]+&fuente=[0-9a-f-]+$/);
  });
});

test.describe.serial('FNC-SMB-003/004 · bandeja, «¿Aplicar siempre?» y deshacer', () => {
  test.beforeAll(async ({ playwright }) => {
    const request = await playwright.request.newContext();
    await setProfile(request, 'simple');
    await request.dispose();
  });

  test.afterAll(async ({ playwright }) => {
    const request = await playwright.request.newContext();
    await setProfile(request, 'estricto');
    await request.dispose();
  });

  test('confirmar en la bandeja y «¿Aplicar siempre?» deja una regla activa', async ({
    page,
  }) => {
    test.setTimeout(90_000);
    await signIn(page, 'sofia@demo.local');
    await page.goto(`/empresas/${ESPIGA}`);
    await expect(page.getByRole('list', { name: 'Pasos del modo simple' })).toBeVisible();
    await expect(page.getByRole('heading', { level: 3, name: /conciliados, \d+ pendientes/ }))
      .toBeVisible();
    await expect(page.getByRole('heading', { name: '¿Cada cuánto subes tu extracto?' }))
      .toBeVisible();

    const inbox = page.getByRole('list', { name: 'Cruces por decidir' });
    const first = inbox.locator('li[data-inbox-item]').filter({ hasText: 'factura uno' });
    await expect(first).toHaveCount(1);
    await expect(first.getByRole('list', { name: 'Por qué aparece' })).toContainText('Mismo valor');
    // La retencion simulada aparece como candidato con su diferencia explicada.
    await expect(inbox.locator('li[data-inbox-item]').filter({ hasText: 'retencion' }))
      .toContainText('posible retención o comisión');

    await first.getByRole('button', { name: 'Confirmar' }).click();
    await expect(first.getByRole('status').filter({ hasText: 'Cruce confirmado' }))
      .toContainText('autorrevisado');
    await first.getByRole('button', { name: '¿Aplicar siempre?' }).click();
    await expect(first.getByRole('status').filter({ hasText: 'Regla activa' }))
      .toContainText('Autorrevisado');

    await page.goto(`/empresas/${ESPIGA}/reglas`);
    const rule = page.getByRole('list', { name: 'Reglas de la empresa' })
      .locator('li[data-rule-status="active"]')
      .filter({ hasText: 'nit fnc syn nit 0091' });
    await expect(rule.first()).toBeVisible();
    await expect(rule.first()).toContainText('Autorrevisada por Sofia Owner');
    await expect(rule.first().getByRole('button', { name: 'Pausar' })).toBeVisible();
  });

  test('aplicar reglas confirma los demas y «Deshacer» los devuelve', async ({ page }) => {
    test.setTimeout(90_000);
    await signIn(page, 'sofia@demo.local');
    await page.goto(`/empresas/${ESPIGA}`);

    await page.getByRole('button', { name: 'Aplicar reglas' }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Reglas aplicadas' }))
      .toContainText('2 cruce(s)');
    const applied = page.getByRole('list', { name: 'Cruces aplicados por regla' });
    await expect(applied.getByText('Regla aprobada', { exact: true })).toHaveCount(2);
    await applied.getByRole('button', { name: 'Deshacer' }).first().click();
    await expect(applied.getByRole('status').filter({ hasText: 'Deshecho' }))
      .toContainText('vuelven a pendientes');

    await page.reload();
    const remaining = page.getByRole('list', { name: 'Aplicaciones de reglas vigentes' });
    await expect(remaining.locator('li')).toHaveCount(1);
    await expect(remaining.getByRole('button', { name: 'Deshacer' })).toBeVisible();
  });
});
