import { permanentRedirectResponse } from '@/lib/permanent-redirect';

export function GET(): Response {
  return permanentRedirectResponse('/privacy');
}

export const HEAD = GET;
