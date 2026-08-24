/**
 * `standalone` empaqueta solo lo que el servidor necesita para arrancar, en vez
 * de copiar `node_modules` entero a la imagen final. La diferencia no es de
 * tamano: cada dependencia que viaja a produccion es superficie que alguien
 * tiene que poder explicar.
 */
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  poweredByHeader: false,
  // La web no habla con nadie mas que con su propia API, y esa llamada la hace
  // el servidor. Si el navegador pudiera llamar a otro origen, el token dejaria
  // de estar solo en una cookie httpOnly.
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'no-referrer' },
          { key: 'X-Frame-Options', value: 'DENY' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data:",
              "connect-src 'self'",
              "frame-ancestors 'none'",
              "form-action 'self'",
              "base-uri 'none'",
            ].join('; '),
          },
        ],
      },
    ];
  },
};

export default nextConfig;
