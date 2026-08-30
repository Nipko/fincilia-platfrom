import { expect, test } from '@playwright/test';

test('TST-UX-BRAND-001: la identidad R2 y sus metadatos son publicos', async ({
  page,
  request,
}) => {
  await page.goto('/entrar');

  const brand = page.getByRole('link', { name: 'Fincilia, ir al inicio' });
  await expect(brand).toBeVisible();
  await expect(brand.locator('.brand-mark__sheet')).toHaveCount(1);
  await expect(brand.locator('.brand-mark__match')).toHaveCount(1);
  await expect(brand.getByText('Conciliación clara')).toBeVisible();

  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
    'href',
    '/manifest.webmanifest',
  );
  await expect(page.locator('link[rel~="icon"][href="/icon.svg"]')).toHaveCount(
    1,
  );

  const manifestResponse = await request.get('/manifest.webmanifest');
  expect(manifestResponse.ok()).toBeTruthy();
  await expect(manifestResponse.json()).resolves.toMatchObject({
    name: 'Fincilia',
    short_name: 'Fincilia',
    start_url: '/',
    display: 'standalone',
  });

  const oauthLogoResponse = await request.get(
    '/brand/fincilia-google-oauth.png',
  );
  expect(oauthLogoResponse.ok()).toBeTruthy();
  expect(oauthLogoResponse.headers()['content-type']).toContain('image/png');
});
