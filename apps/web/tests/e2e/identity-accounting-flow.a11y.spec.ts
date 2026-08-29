import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const COMPANY_ID = '161b0037-c445-50aa-b400-72632d3f53f0';

async function signIn(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('ana@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

async function expectNoSeriousOrCriticalViolations(page: Page): Promise<void> {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
    .analyze();
  const blocking = result.violations
    .filter(
      (violation) =>
        violation.impact === 'serious' || violation.impact === 'critical',
    )
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      targets: violation.nodes.map((node) => node.target),
    }));

  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

test('TST-A11Y-001: centro de identidad sin hallazgos serios o criticos', async ({
  page,
}) => {
  await signIn(page);
  await page.goto('/cuenta');

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: flujo contable sin hallazgos serios o criticos', async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/empresas/${COMPANY_ID}/flujo-contable`);

  await expectNoSeriousOrCriticalViolations(page);
});
