import { expect, test } from '@playwright/test';

test('TST-REG-005/006: una persona crea cuenta y primer espacio sin semillas', async ({
  page,
}) => {
  const marker = `${Date.now()}-${test.info().retry}`;
  const username = `inicio.${marker}@demo.local`;
  const firmName = `Firma Inicio Sintetica ${marker}`;
  const companyName = `Empresa Inicio Sintetica ${marker}`;
  const password = 'Registro-Demo-2026!';

  await page.goto('/entrar');
  await page.getByRole('link', { name: 'Crear una cuenta' }).click();
  await expect(page).toHaveURL(/\/registro$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Crea tu cuenta' }))
    .toBeVisible();

  await page.getByLabel('Tu nombre visible').fill(`Persona Inicio ${marker}`);
  await page.getByLabel('Nombre de tu firma o equipo').fill(firmName);
  await page.getByLabel('Correo sintetico').fill(username);
  await page.getByLabel('Contrasena', { exact: true }).fill(password);
  await page.getByLabel('Confirma la contrasena').fill(password);
  await page.getByRole('button', { name: 'Crear cuenta y configurar empresa' }).click();

  await expect(page).toHaveURL(/\/empresas\/nueva\?inicio=registro$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Nueva empresa' }))
    .toBeVisible();
  await expect(page.getByLabel('Firma responsable')).toContainText(firmName);

  await page.getByLabel('Razon social').fill(companyName);
  await page.getByLabel('Identificacion tributaria sintetica')
    .fill(`SYN-TAX-${marker}`);
  await page.getByLabel('Nombre visible de la cuenta').fill('Cuenta de inicio');
  await page.getByLabel('Identificador sintetico de cuenta')
    .fill(`SYN-ACCOUNT-${marker}`);
  await page.getByLabel('Nombre visible de la fuente').fill('Fuente de inicio');
  await page.getByRole('button', { name: 'Crear empresa y continuar' }).click();

  await expect(page).toHaveURL(/\/empresas\/[0-9a-f-]+\/fuentes\?alta=creada$/);
  await expect(page.getByRole('status').filter({ hasText: 'Empresa creada' }))
    .toBeVisible();
  await expect(page.getByRole('row', { name: /Cuenta de inicio/ })).toBeVisible();
  await expect(page.getByRole('rowheader', { name: 'Fuente de inicio' })).toBeVisible();
});
