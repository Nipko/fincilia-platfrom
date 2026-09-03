import { permanentRedirectResponse } from '@/lib/permanent-redirect';

export function GET(): Response {
  return permanentRedirectResponse('/terms');
}

export const HEAD = GET;
