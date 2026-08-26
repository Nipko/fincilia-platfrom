import { expect, type APIRequestContext, type Page } from '@playwright/test';

const API_URL = process.env.FINCILIA_E2E_API_URL ?? 'http://127.0.0.1:58080';
export const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';

function bogotaDate(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Bogota', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
}

async function session(
  request: APIRequestContext,
  username: string,
): Promise<{ token: string; subject_id: string }> {
  const response = await request.post(`${API_URL}/api/v1/auth/session`, {
    data: { username, secret: 'fincilia-demo-only' },
  });
  expect(response.ok()).toBeTruthy();
  return await response.json() as { token: string; subject_id: string };
}

export async function ensureSyntheticReminder(
  request: APIRequestContext,
): Promise<{ sourceId: string; sourceName: string; localDate: string }> {
  const [owner, preparer] = await Promise.all([
    session(request, 'sofia@demo.local'),
    session(request, 'ana@demo.local'),
  ]);
  const localDate = bogotaDate();
  const sourceName = `Ciclo sintetico E2E OPS-001 ${localDate}`;
  const headers = { authorization: `Bearer ${owner.token}` };
  const listed = await request.get(
    `${API_URL}/api/v1/companies/${ESPIGA}/sources`, { headers },
  );
  expect(listed.ok()).toBeTruthy();
  const sources = await listed.json() as Array<{
    data_source_id: string;
    display_name: string;
  }>;
  let sourceId = sources.find((source) => source.display_name === sourceName)
    ?.data_source_id;
  if (!sourceId) {
    const created = await request.post(
      `${API_URL}/api/v1/companies/${ESPIGA}/sources`, {
        headers,
        data: {
          source_family: 'bank_account',
          display_name: sourceName,
          purpose_code: 'operational',
          timezone: 'America/Bogota',
        },
      },
    );
    expect(created.ok()).toBeTruthy();
    sourceId = (await created.json()).data_source_id as string;
  }

  const detail = await request.get(
    `${API_URL}/api/v1/companies/${ESPIGA}/sources/${sourceId}`, { headers },
  );
  expect(detail.ok()).toBeTruthy();
  const existing = await detail.json() as { cycle: { anchor_date: string } | null };
  if (!existing.cycle || existing.cycle.anchor_date !== localDate) {
    const cycled = await request.put(
      `${API_URL}/api/v1/companies/${ESPIGA}/sources/${sourceId}/cycle`, {
        headers,
        data: {
          periodicity: 'custom', custom_days: 1, due_day_offset: 0,
          grace_days: 2, responsible_subject_id: preparer.subject_id,
          timezone: 'America/Bogota', anchor_date: localDate,
        },
      },
    );
    expect(cycled.ok()).toBeTruthy();
  }
  const generated = await request.post(
    `${API_URL}/api/v1/companies/${ESPIGA}/sources/${sourceId}/expectations`, {
      headers, data: { until: localDate },
    },
  );
  expect(generated.ok()).toBeTruthy();
  return { sourceId, sourceName, localDate };
}

export async function signInOwner(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('sofia@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

export async function signInReviewer(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('beto@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}
