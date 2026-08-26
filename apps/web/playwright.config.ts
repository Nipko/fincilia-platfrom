import { defineConfig, devices } from '@playwright/test';

const baseURL =
  process.env.FINCILIA_E2E_BASE_URL ?? 'http://127.0.0.1:53000';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  // Los recorridos usan el mismo tenant sintetico y prueban revocacion real.
  // Versionar su autorizacion invalida correctamente las demas sesiones; por eso
  // este proyecto compartido es serial tanto localmente como en CI.
  workers: 1,
  reporter: process.env.CI ? 'line' : 'list',
  outputDir: './tmp/playwright-results',
  expect: {
    timeout: 5_000,
  },
  use: {
    baseURL,
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
    colorScheme: 'light',
    contextOptions: {
      reducedMotion: 'reduce',
    },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      testIgnore: /\.a11y\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'accessibility',
      testMatch: /\.a11y\.spec\.ts$/,
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
