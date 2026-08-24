import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

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

test('TST-A11Y-001: ingreso publico sin hallazgos serios o criticos', async ({
  page,
}) => {
  await page.goto('/entrar');

  await expectNoSeriousOrCriticalViolations(page);
});

test('TST-A11Y-001: no encontrado conserva la misma base accesible', async ({
  page,
}) => {
  await page.goto('/ruta-sintetica-inexistente');

  await expectNoSeriousOrCriticalViolations(page);
});
