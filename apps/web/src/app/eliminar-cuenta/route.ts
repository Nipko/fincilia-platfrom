import { permanentRedirectResponse } from '@/lib/permanent-redirect';

export function GET(): Response {
  return permanentRedirectResponse('/delete-account');
}

export const HEAD = GET;
