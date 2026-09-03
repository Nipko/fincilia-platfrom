import { permanentRedirectResponse } from '@/lib/permanent-redirect';

export function GET(): Response {
  return permanentRedirectResponse('/subprocessors');
}

export const HEAD = GET;
