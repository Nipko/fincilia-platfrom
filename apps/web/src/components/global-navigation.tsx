'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { AppIcon, type AppIconName } from './app-icon';

const GROUPS: readonly {
  label: string;
  items: readonly { href: string; label: string; icon: AppIconName }[];
}[] = [
  {
    label: 'Operación',
    items: [
      { href: '/empresas', label: 'Portafolio', icon: 'portfolio' },
      { href: '/revisiones', label: 'Revisiones', icon: 'reviews' },
      { href: '/recordatorios', label: 'Ciclos', icon: 'cycles' },
    ],
  },
  {
    label: 'Control',
    items: [
      { href: '/calidad', label: 'Calidad', icon: 'quality' },
      { href: '/preparacion-cierre', label: 'Cierre', icon: 'close' },
      { href: '/informes', label: 'Informes', icon: 'reports' },
    ],
  },
  {
    label: 'Administración',
    items: [
      { href: '/auditoria', label: 'Auditoría', icon: 'audit' },
      { href: '/cuenta', label: 'Cuenta', icon: 'account' },
    ],
  },
] as const;

function isCurrent(pathname: string, href: string): boolean {
  if (href === '/empresas') return pathname === href || pathname.startsWith('/empresas/');
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function GlobalNavigation({
  authenticated,
  displayName = 'Cuenta',
}: {
  authenticated: boolean;
  displayName?: string;
}) {
  const pathname = usePathname();

  if (!authenticated || pathname === '/entrar') {
    return null;
  }

  return <>
    <nav aria-label="Navegacion principal" className="global-nav sidebar-nav">
      {GROUPS.map((group) => (
        <div className="sidebar-nav__group" key={group.label}>
          <span className="sidebar-nav__label">{group.label}</span>
          <div className="sidebar-nav__items">
            {group.items.map((item) => {
              const current = isCurrent(pathname, item.href);
              return (
                <Link
                  aria-current={current ? 'page' : undefined}
                  href={item.href}
                  key={item.href}
                >
                  <AppIcon name={item.icon} />
                  <span>{item.label}</span>
                  {current ? <span aria-hidden="true" className="nav-current-dot" /> : null}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
    <Link className="sidebar-account" href="/cuenta">
      <span aria-hidden="true" className="sidebar-account__avatar">
        {displayName.slice(0, 1).toUpperCase()}
      </span>
      <span><strong>{displayName}</strong><small>Ver cuenta y acceso</small></span>
      <span aria-hidden="true" className="sidebar-account__arrow">›</span>
    </Link>
  </>;
}
