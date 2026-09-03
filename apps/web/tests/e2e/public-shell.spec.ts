import { expect, test } from '@playwright/test';

test.describe('recorrido publico sin secretos', () => {
  test('la pagina de ingreso tiene formulario etiquetado y skip link funcional', async ({
    page,
  }) => {
    const response = await page.goto('/entrar');

    expect(response?.headers()).toMatchObject({
      'x-content-type-options': 'nosniff',
      'x-frame-options': 'DENY',
      'referrer-policy': 'no-referrer',
      'permissions-policy': 'camera=(), microphone=(), geolocation=(), payment=()',
      'cross-origin-opener-policy': 'same-origin-allow-popups',
      'cross-origin-resource-policy': 'same-origin',
      'x-permitted-cross-domain-policies': 'none',
    });
    const contentSecurityPolicy = response?.headers()['content-security-policy'] ?? '';
    expect(contentSecurityPolicy).toContain("object-src 'none'");
    expect(contentSecurityPolicy).toContain("frame-src 'none'");
    expect(contentSecurityPolicy).not.toContain("'unsafe-eval'");

    await expect(page.getByRole('heading', { level: 1, name: 'Fincilia' })).toBeVisible();
    await expect(page.getByLabel('Usuario')).toBeVisible();
    await expect(page.getByLabel('Contrasena')).toHaveAttribute('type', 'password');
    await expect(page.getByRole('link', { name: 'Crear una cuenta' }))
      .toHaveAttribute('href', '/registro');
    await expect(page.getByRole('link', { name: 'terminos del servicio' }))
      .toHaveAttribute('href', '/terms');

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
    await expect(page.getByText('Entorno UAT · identidad administrada pendiente de activación.'))
      .toBeVisible();
    await expect(page.getByText(/No pedirá acceso a Gmail, Drive/)).toBeVisible();
    await page.getByRole('link', { name: 'Leer política de privacidad' }).click();

    await expect(page).toHaveURL(/\/privacy$/);
    await expect(page.getByRole('heading', { level: 1, name: 'Privacy Policy' }))
      .toBeVisible();
    await expect(page.locator('main.legal-page')).toHaveAttribute('lang', 'en');
    await expect(page.locator('link[rel="canonical"]'))
      .toHaveAttribute('href', 'https://fincilia.com/privacy');
    await expect(page.getByText('Current policy')).toBeVisible();
    await expect(page.getByText(/Version privacy-2026-09-03-en/)).toBeVisible();
    await expect(page.getByText(/Parallext LLC/).first()).toBeVisible();
    await expect(page.getByText(/privacy@fincilia.com/).first()).toBeVisible();

    for (const [path, heading] of [
      ['/terms', 'Terms of Service'],
      ['/cookies', 'Cookie Notice'],
      ['/security', 'Security at Fincilia'],
      ['/dpa', 'Data Processing Agreement (DPA)'],
      ['/subprocessors', 'Subprocessors and providers'],
      ['/delete-account', 'Account and Data Deletion'],
    ] as const) {
      await page.goto(path);
      await expect(page.locator('main.legal-page')).toHaveAttribute('lang', 'en');
      await expect(page.getByRole('heading', { level: 1, name: heading })).toBeVisible();
      await expect(page.locator('link[rel="canonical"]'))
        .toHaveAttribute('href', `https://fincilia.com${path}`);
    }
  });

  test('las rutas legales anteriores redirigen permanentemente a las canonicas', async ({
    request,
  }) => {
    for (const [legacyPath, canonicalPath] of [
      ['/privacidad', '/privacy'],
      ['/terminos', '/terms'],
      ['/seguridad', '/security'],
      ['/subencargados', '/subprocessors'],
      ['/eliminar-cuenta', '/delete-account'],
    ] as const) {
      const response = await request.get(legacyPath, { maxRedirects: 0 });
      expect(response.status()).toBe(308);
      expect(response.headers().location).toBe(canonicalPath);
    }
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
