import type { Metadata, Viewport } from 'next';
import type { ReactNode } from 'react';
import Link from 'next/link';

import { BrandMark } from '@/components/brand-mark';
import { GlobalNavigation } from '@/components/global-navigation';
import { fetchMe } from '@/lib/api';
import { publicStage } from '@/lib/public-stage';
import { readSession } from '@/lib/session';

import './globals.css';

export const metadata: Metadata = {
  title: 'Fincilia',
  description: 'Conciliación, limpieza y control financiero explicable para contadores y PYMEs.',
  icons: {
    icon: [
      { url: '/icon.svg', type: 'image/svg+xml' },
      { url: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
    ],
    apple: [{ url: '/icons/apple-touch-icon.png', sizes: '180x180', type: 'image/png' }],
  },
  manifest: '/manifest.webmanifest',
};

export const viewport: Viewport = {
  colorScheme: 'light dark',
  themeColor: '#087957',
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await readSession();
  const stage = publicStage(process.env.FINCILIA_PUBLIC_STAGE);
  const authenticated = session !== null;
  let platformAccess = false;
  if (session) {
    try {
      const me = await fetchMe(session.token);
      platformAccess = me.platform_roles.length > 0;
    } catch {
      // La navegación nunca convierte una caída de API en autorización local.
      platformAccess = false;
    }
  }

  return (
    <html lang="es">
      <body className={authenticated ? 'app-body' : 'public-body'}>
        <a className="skip-link" href="#main-content">
          Saltar al contenido principal
        </a>
        {authenticated ? (
          <div className="app-frame">
            <aside className="app-sidebar">
              <div className="app-sidebar__brand">
                <BrandMark />
                <span className="environment-badge">
                  <span aria-hidden="true" />{stage.badge}
                </span>
              </div>
              <GlobalNavigation authenticated displayName={session.displayName}
                platformAccess={platformAccess} />
              <div className="app-sidebar__trust">
                <span aria-hidden="true">◆</span>
                <p><strong>Contexto protegido</strong><small>Empresa y permisos se validan en el servidor.</small></p>
              </div>
            </aside>
            <div className="app-workspace">
              <header className="app-topbar">
                <div>
                  <span className="app-topbar__pulse" aria-hidden="true" />
                  Espacio de trabajo seguro
                </div>
                <Link href="/cuenta">{session.displayName}<span aria-hidden="true">↗</span></Link>
              </header>
              <div className="shell app-content" id="main-content" tabIndex={-1}>{children}</div>
              <footer className="app-footer">
                <span>Fincilia · <a href="https://parallext.com" rel="noreferrer" target="_blank">Parallext.com</a></span>
                <nav aria-label="Legal y confianza">
                  <Link href="/privacidad">Privacidad</Link>
                  <Link href="/seguridad">Seguridad</Link>
                </nav>
              </footer>
            </div>
          </div>
        ) : <>
          <header className="product-bar">
            <div className="product-bar__inner">
              <BrandMark />
              <span className="environment-badge">
                <span aria-hidden="true" />{stage.badge}
              </span>
            </div>
          </header>
          <div className="shell" id="main-content" tabIndex={-1}>{children}</div>
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
            <span>{stage.footer}</span>
          </footer>
        </>}
      </body>
    </html>
  );
}
