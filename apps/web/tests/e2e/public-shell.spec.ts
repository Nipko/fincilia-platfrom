import { expect, test } from '@playwright/test';

test.describe('recorrido publico sin secretos', () => {
  test('la pagina de ingreso tiene formulario etiquetado y skip link funcional', async ({
    page,
  }) => {
    await page.goto('/entrar');

    await expect(page.getByRole('heading', { level: 1, name: 'Fincilia' })).toBeVisible();
    await expect(page.getByLabel('Usuario')).toBeVisible();
    await expect(page.getByLabel('Contrasena')).toHaveAttribute('type', 'password');
    await expect(page.getByRole('link', { name: 'Crear una cuenta' }))
      .toHaveAttribute('href', '/registro');
    await expect(page.getByRole('link', { name: 'terminos del servicio' }))
      .toHaveAttribute('href', '/terminos');

    await page.keyboard.press('Tab');
    const skipLink = page.getByRole('link', {
      name: 'Saltar al contenido principal',
    });
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toHaveAttribute('href', '#main-content');
    await skipLink.press('Enter');
    await expect(page.locator('#main-content')).toBeFocused();
  });

  test('el registro sintetico explica los dos pasos y protege el secreto', async ({
    page,
  }) => {
    await page.goto('/registro');

    await expect(page.getByRole('heading', { level: 1, name: 'Crea tu cuenta' }))
      .toBeVisible();
    await expect(page.getByLabel('Correo sintetico'))
      .toHaveAttribute('type', 'email');
    await expect(page.getByLabel('Código de invitación')).toBeVisible();
    await expect(page.getByLabel('Contrasena', { exact: true }))
      .toHaveAttribute('autocomplete', 'new-password');
    await expect(page.getByLabel('Confirma la contrasena'))
      .toHaveAttribute('type', 'password');
    await expect(page.getByRole('link', { name: 'Volver a entrar' }))
      .toHaveAttribute('href', '/entrar');
    await expect(page.getByLabel(/solo puedo usar nombres/)).toHaveAttribute('required', '');
    await expect(page.getByLabel(/Acepto los terminos/)).toHaveAttribute('required', '');
  });

  test('la portada y el centro legal son publicos y transparentes', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', {
      level: 1,
      name: 'De documentos dispersos a diferencias explicables.',
    })).toBeVisible();
    await expect(page.getByText('Registro público con Google · datos reales pendientes de autorización'))
      .toBeVisible();
    await expect(page.getByText(/No pedirá acceso a Gmail, Drive/)).toBeVisible();
    await page.getByRole('link', { name: 'Leer política de privacidad' }).click();

    await expect(page).toHaveURL(/\/privacidad$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Política de privacidad' }))
      .toBeVisible();
    await expect(page.getByText('Borrador de preproducción')).toBeVisible();
    await expect(page.getByText(/support@parallext.com/).first()).toBeVisible();
  });

  test('una ruta protegida sin sesion vuelve al ingreso', async ({ page }) => {
    await page.goto('/empresas');

    await expect(page).toHaveURL(/\/entrar$/);
    await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible();
  });

  test('una ruta inexistente usa la frontera de no encontrado', async ({ page }) => {
    const response = await page.goto('/ruta-sintetica-inexistente');

    expect(response?.status()).toBe(404);
    await expect(
      page.getByRole('heading', {
        level: 1,
        name: 'No encontramos esta página',
      }),
    ).toBeVisible();
    await expect(page.getByRole('link', { name: 'Volver al inicio' })).toBeVisible();
  });
});
