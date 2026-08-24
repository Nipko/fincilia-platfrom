import { expect, test } from '@playwright/test';

test.describe('recorrido publico sin secretos', () => {
  test('la pagina de ingreso tiene formulario etiquetado y skip link funcional', async ({
    page,
  }) => {
    await page.goto('/entrar');

    await expect(page.getByRole('heading', { level: 1, name: 'Fincilia' })).toBeVisible();
    await expect(page.getByLabel('Usuario')).toBeVisible();
    await expect(page.getByLabel('Contrasena')).toHaveAttribute('type', 'password');

    await page.keyboard.press('Tab');
    const skipLink = page.getByRole('link', {
      name: 'Saltar al contenido principal',
    });
    await expect(skipLink).toBeFocused();
    await expect(skipLink).toHaveAttribute('href', '#main-content');
    await skipLink.press('Enter');
    await expect(page.locator('#main-content')).toBeFocused();
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
