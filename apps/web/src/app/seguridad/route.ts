import { permanentRedirectResponse } from '@/lib/permanent-redirect';

export function GET(): Response {
  return permanentRedirectResponse('/security');
}

export const HEAD = GET;
