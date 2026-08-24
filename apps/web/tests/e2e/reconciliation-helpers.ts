import { expect, type APIRequestContext, type Page } from '@playwright/test';

const API_URL = process.env.FINCILIA_E2E_API_URL ?? 'http://127.0.0.1:58080';
export const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';

export async function signInReviewer(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('beto@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

export async function findReviewPair(
  request: APIRequestContext,
  status?: 'open' | 'confirmed' | 'rejected',
): Promise<{ left: string; right: string }> {
  const signed = await request.post(`${API_URL}/api/v1/auth/session`, {
    data: { username: 'beto@demo.local', secret: 'fincilia-demo-only' },
  });
  expect(signed.ok()).toBeTruthy();
  const token = (await signed.json()).token as string;
  const headers = { authorization: `Bearer ${token}` };
  const datasetsResponse = await request.get(
    `${API_URL}/api/v1/companies/${ESPIGA}/datasets`,
    { headers },
  );
  expect(datasetsResponse.ok()).toBeTruthy();
  const datasets = (await datasetsResponse.json()) as Array<{
    dataset_version_id: string;
    state: string;
  }>;
  const eligible = datasets.filter((item) =>
    item.state === 'validated' || item.state === 'published');

  for (let leftIndex = 0; leftIndex < eligible.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < eligible.length; rightIndex += 1) {
      const left = eligible[leftIndex]!.dataset_version_id;
      const right = eligible[rightIndex]!.dataset_version_id;
      const reviewsResponse = await request.get(
        `${API_URL}/api/v1/companies/${ESPIGA}/reconciliation/reviews`,
        { headers, params: { left_dataset_id: left, right_dataset_id: right } },
      );
      if (!reviewsResponse.ok()) continue;
      const reviews = (await reviewsResponse.json()) as Array<{ status: string }>;
      if (reviews.some((review) => !status || review.status === status)) {
        return { left, right };
      }
    }
  }
  throw new Error(`No synthetic ${status ?? 'any'} review pair was found`);
}

export function reviewUrl(pair: { left: string; right: string }): string {
  const query = new URLSearchParams({
    izquierda: pair.left,
    derecha: pair.right,
    ventana: '3',
    pagina: '0',
  });
  return `/empresas/${ESPIGA}/conciliacion?${query.toString()}`;
}
