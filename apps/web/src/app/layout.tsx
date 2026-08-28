import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import Link from 'next/link';

import { BrandMark } from '@/components/brand-mark';
import { GlobalNavigation } from '@/components/global-navigation';
import { readSession } from '@/lib/session';

import './globals.css';

export const metadata: Metadata = {
  title: 'Fincilia',
  description: 'Conciliación, limpieza y control financiero explicable para contadores y PYMEs.',
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await readSession();
  const closedBeta = process.env.FINCILIA_PUBLIC_STAGE === 'closed_beta';

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
              {closedBeta ? 'Beta cerrada' : 'Entorno local'}
            </span>
          </div>
        </header>
        <div className="shell" id="main-content" tabIndex={-1}>
          {children}
        </div>
        <footer className="ceiling public-footer">
          <div>
            <strong>Fincilia</strong>
            <span>Desarrollado por <a href="https://parallext.com" rel="noreferrer" target="_blank">Parallext.com</a></span>
          </div>
          <nav aria-label="Legal y confianza">
            <Link href="/privacidad">Privacidad</Link>
            <Link href="/terminos">Términos</Link>
            <Link href="/cookies">Cookies</Link>
            <Link href="/seguridad">Seguridad</Link>
            <Link href="/eliminar-cuenta">Eliminar cuenta</Link>
          </nav>
          <span>{closedBeta ? 'Beta cerrada' : 'Entorno local'} · datos sintéticos</span>
        </footer>
      </body>
    </html>
  );
}
