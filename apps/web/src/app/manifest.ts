import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Fincilia',
    short_name: 'Fincilia',
    description: 'Conciliación, limpieza y control financiero explicable para contadores y PYMEs.',
    start_url: '/',
    display: 'standalone',
    background_color: '#f4f7f5',
    theme_color: '#087957',
    icons: [
      {
        src: '/icons/icon-192.png',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: '/icons/icon-512.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  };
}
