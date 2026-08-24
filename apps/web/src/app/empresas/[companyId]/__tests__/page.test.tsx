import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => {
  class ApiError extends Error {
    readonly status: number;

    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  }
  return {
    ApiError,
    fetchCompany: vi.fn(),
    notFound: vi.fn((): never => {
      throw new Error('NEXT_NOT_FOUND');
    }),
    readSession: vi.fn(),
    redirect: vi.fn((): never => {
      throw new Error('NEXT_REDIRECT');
    }),
  };
});

vi.mock('next/navigation', () => ({
  notFound: mocks.notFound,
  redirect: mocks.redirect,
}));
vi.mock('@/lib/session', () => ({ readSession: mocks.readSession }));
vi.mock('@/lib/api', () => ({
  ApiError: mocks.ApiError,
  fetchAudit: vi.fn(),
  fetchCompany: mocks.fetchCompany,
  fetchDocuments: vi.fn(),
  fetchSourcesFull: vi.fn(),
}));

import CompanyPage from '../page';

describe('CompanyPage boundaries', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.readSession.mockResolvedValue({
      token: 'token-sintetico',
      displayName: 'Ada',
    });
  });

  it('usa la frontera 404 para una empresa inexistente', async () => {
    mocks.fetchCompany.mockRejectedValue(new mocks.ApiError(404, 'not found'));

    await expect(
      CompanyPage({
        params: Promise.resolve({
          companyId: '5f0f7b18-0a7a-5c8e-9d2c-6a1f2b3c4d5e',
        }),
        searchParams: Promise.resolve({}),
      }),
    ).rejects.toThrow('NEXT_NOT_FOUND');
    expect(mocks.notFound).toHaveBeenCalledOnce();
  });
});
