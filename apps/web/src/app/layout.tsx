import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { BrandMark } from '@/components/brand-mark';
import { GlobalNavigation } from '@/components/global-navigation';
import { readSession } from '@/lib/session';

import './globals.css';

export const metadata: Metadata = {
  title: 'Fincilia',
  description: 'Conciliacion y cierre. Entorno local con datos sinteticos.',
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await readSession();

  return (
    <html lang="es">
      <body>
        <a className="skip-link" href="#main-content">
          Saltar al contenido principal
        </a>
        <header className="product-bar">
          <div className="product-bar__inner">
            <BrandMark />
            <GlobalNavigation authenticated={session !== null} />
            <span className="environment-badge">
              <span aria-hidden="true" />
              Entorno local
            </span>
          </div>
        </header>
        <div className="shell" id="main-content" tabIndex={-1}>
          {children}
        </div>
        <footer className="ceiling">
          <strong>Fincilia</strong>
          <span>Entorno local · datos sinteticos · sin proveedores externos</span>
        </footer>
      </body>
    </html>
  );
}
