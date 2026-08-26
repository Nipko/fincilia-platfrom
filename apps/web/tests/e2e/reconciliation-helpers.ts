import { expect, type APIRequestContext, type Page } from '@playwright/test';

const API_URL = process.env.FINCILIA_E2E_API_URL ?? 'http://127.0.0.1:58080';
export const ESPIGA = '161b0037-c445-50aa-b400-72632d3f53f0';
const CANDIDATE_PAGE_SIZE = 25;
const CANDIDATE_BATCH_SIZE = 200;
const MAX_CANDIDATE_OFFSET = 10_000;

type ReviewStatus = 'open' | 'confirmed' | 'rejected';

export type ReviewPair = {
  candidateId: string;
  left: string;
  right: string;
  maxDays: number;
  page: number;
  status: ReviewStatus;
  confirmationConflict: boolean;
};

export type GroupComposition = {
  left: string;
  right: string;
  anchorSide: 'left' | 'right';
  anchorMovementId: string;
  relatedMovementIds: string[];
};

type ReviewSummary = {
  candidate_id: string;
  left_movement_id: string;
  right_movement_id: string;
  left_dataset_id: string;
  right_dataset_id: string;
  date_window_days: number;
  status: ReviewStatus;
  confirmation_conflict: boolean;
};

type CandidateBatch = {
  truncated: boolean;
  candidates: Array<{
    left: { movement_id: string };
    right: { movement_id: string };
  }>;
};

export async function signInReviewer(page: Page): Promise<void> {
  await page.goto('/entrar');
  await page.getByLabel('Usuario').fill('beto@demo.local');
  await page.getByLabel('Contrasena').fill('fincilia-demo-only');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(/\/empresas$/);
}

export async function findReviewPair(
  request: APIRequestContext,
  preferredStatus?: ReviewStatus,
): Promise<ReviewPair> {
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
  const fallback: ReviewSummary[] = [];

  for (let leftIndex = 0; leftIndex < eligible.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < eligible.length; rightIndex += 1) {
      const left = eligible[leftIndex]!.dataset_version_id;
      const right = eligible[rightIndex]!.dataset_version_id;
      const reviewsResponse = await request.get(
        `${API_URL}/api/v1/companies/${ESPIGA}/reconciliation/reviews`,
        { headers, params: { left_dataset_id: left, right_dataset_id: right } },
      );
      if (!reviewsResponse.ok()) continue;
      const reviews = (await reviewsResponse.json()) as ReviewSummary[];
      for (const review of reviews) {
        if (preferredStatus && review.status !== preferredStatus) {
          fallback.push(review);
          continue;
        }
        const located = await locateReviewPage(request, headers, review);
        if (located) return located;
      }
    }
  }

  // Un ledger persistente no se reabre ni se borra para repetir una prueba. Si
  // la revision solicitada ya es terminal, devolvemos esa version para verificar
  // que la UI conserva historia y no ofrece una segunda decision.
  for (const review of fallback) {
    const located = await locateReviewPage(request, headers, review);
    if (located) return located;
  }
  throw new Error(`No synthetic ${preferredStatus ?? 'any'} review pair was found`);
}

export async function findGroupComposition(
  request: APIRequestContext,
): Promise<GroupComposition> {
  const pair = await findReviewPair(request);
  const signed = await request.post(`${API_URL}/api/v1/auth/session`, {
    data: { username: 'ana@demo.local', secret: 'fincilia-demo-only' },
  });
  expect(signed.ok()).toBeTruthy();
  const token = (await signed.json()).token as string;
  const headers = { authorization: `Bearer ${token}` };
  const [leftResponse, rightResponse] = await Promise.all([
    request.get(
      `${API_URL}/api/v1/companies/${ESPIGA}/datasets/${pair.left}/movements`,
      { headers, params: { offset: 0, limit: 50 } },
    ),
    request.get(
      `${API_URL}/api/v1/companies/${ESPIGA}/datasets/${pair.right}/movements`,
      { headers, params: { offset: 0, limit: 50 } },
    ),
  ]);
  expect(leftResponse.ok()).toBeTruthy();
  expect(rightResponse.ok()).toBeTruthy();
  type Movement = {
    movement_id: string;
    currency: string;
    direction: string;
  };
  const left = await leftResponse.json() as Movement[];
  const right = await rightResponse.json() as Movement[];

  for (const anchor of left) {
    const related = right.filter((movement) => (
      movement.currency === anchor.currency &&
      movement.direction !== anchor.direction
    ));
    if (related.length >= 2) {
      return {
        left: pair.left,
        right: pair.right,
        anchorSide: 'left',
        anchorMovementId: anchor.movement_id,
        relatedMovementIds: related.slice(0, 2).map((item) => item.movement_id),
      };
    }
  }
  for (const anchor of right) {
    const related = left.filter((movement) => (
      movement.currency === anchor.currency &&
      movement.direction !== anchor.direction
    ));
    if (related.length >= 2) {
      return {
        left: pair.left,
        right: pair.right,
        anchorSide: 'right',
        anchorMovementId: anchor.movement_id,
        relatedMovementIds: related.slice(0, 2).map((item) => item.movement_id),
      };
    }
  }
  throw new Error('No synthetic 1:N or N:1 composition was found');
}

function movementPair(left: string, right: string): string {
  return [left, right].sort().join(':');
}

async function locateReviewPage(
  request: APIRequestContext,
  headers: { authorization: string },
  review: ReviewSummary,
): Promise<ReviewPair | null> {
  const expected = movementPair(review.left_movement_id, review.right_movement_id);
  for (let offset = 0; offset <= MAX_CANDIDATE_OFFSET; offset += CANDIDATE_BATCH_SIZE) {
    const response = await request.get(
      `${API_URL}/api/v1/companies/${ESPIGA}/reconciliation/candidates`,
      {
        headers,
        params: {
          left_dataset_id: review.left_dataset_id,
          right_dataset_id: review.right_dataset_id,
          max_days: review.date_window_days,
          offset,
          limit: CANDIDATE_BATCH_SIZE,
        },
      },
    );
    if (!response.ok()) break;
    const batch = (await response.json()) as CandidateBatch;
    const index = batch.candidates.findIndex((candidate) =>
      movementPair(candidate.left.movement_id, candidate.right.movement_id) === expected);
    if (index >= 0) {
      return {
        candidateId: review.candidate_id,
        left: review.left_dataset_id,
        right: review.right_dataset_id,
        maxDays: review.date_window_days,
        page: Math.floor((offset + index) / CANDIDATE_PAGE_SIZE),
        status: review.status,
        confirmationConflict: review.confirmation_conflict,
      };
    }
    if (!batch.truncated) break;
  }
  return null;
}

export async function findPublishedDataset(
  request: APIRequestContext,
): Promise<{ artifactId: string; datasetId: string; rows: number }> {
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
    artifact_id: string;
    state: string;
    movement_count: number;
  }>;
  const published = datasets
    .filter((item) => item.state === 'published')
    .sort((left, right) => left.movement_count - right.movement_count);

  for (const candidate of published) {
    const detailResponse = await request.get(
      `${API_URL}/api/v1/companies/${ESPIGA}/datasets/` +
        candidate.dataset_version_id,
      { headers },
    );
    if (!detailResponse.ok()) continue;
    const detail = (await detailResponse.json()) as {
      completeness_state: string;
      lineage_state: string;
      manifest: { reproducible: boolean } | null;
    };
    if (
      detail.completeness_state === 'verified' &&
      detail.lineage_state === 'complete' &&
      detail.manifest?.reproducible === true
    ) {
      return {
        artifactId: candidate.artifact_id,
        datasetId: candidate.dataset_version_id,
        rows: candidate.movement_count,
      };
    }
  }
  throw new Error('No eligible synthetic published dataset was found');
}

export function publishedDatasetUrl(dataset: {
  artifactId: string;
  datasetId: string;
}): string {
  const query = new URLSearchParams({ dataset: dataset.datasetId });
  return (
    `/empresas/${ESPIGA}/documentos/${dataset.artifactId}/mapeo?` +
    query.toString()
  );
}

export function reviewUrl(pair: ReviewPair): string {
  const query = new URLSearchParams({
    izquierda: pair.left,
    derecha: pair.right,
    ventana: String(pair.maxDays),
    pagina: String(pair.page),
    revision: pair.candidateId,
  });
  return `/empresas/${ESPIGA}/conciliacion?${query.toString()}#revision-${pair.candidateId}`;
}

export function groupUrl(group: Pick<GroupComposition, 'left' | 'right'>): string {
  const query = new URLSearchParams({
    izquierda: group.left,
    derecha: group.right,
    ventana: '3',
    pagina: '0',
  });
  return `/empresas/${ESPIGA}/conciliacion?${query.toString()}#group-proposals-title`;
}
