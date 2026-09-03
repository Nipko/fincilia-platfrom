export function permanentRedirectResponse(destination: string): Response {
  if (!destination.startsWith('/') || destination.startsWith('//')) {
    throw new Error('permanent redirects must target an absolute local path');
  }
  return new Response(null, {
    status: 308,
    headers: { location: destination },
  });
}
