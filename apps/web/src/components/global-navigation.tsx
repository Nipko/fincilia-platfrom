'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ITEMS = [
  { href: '/empresas', label: 'Portafolio' },
  { href: '/revisiones', label: 'Revisiones' },
  { href: '/recordatorios', label: 'Ciclos' },
  { href: '/calidad', label: 'Calidad' },
  { href: '/informes', label: 'Informes' },
  { href: '/preparacion-cierre', label: 'Cierre' },
  { href: '/auditoria', label: 'Auditoria' },
  { href: '/cuenta', label: 'Cuenta' },
] as const;

export function GlobalNavigation({ authenticated }: { authenticated: boolean }) {
  const pathname = usePathname();

  if (!authenticated || pathname === '/entrar') {
    return null;
  }

  return (
    <nav aria-label="Navegacion principal" className="global-nav">
      {ITEMS.map((item) => {
        const current =
          item.href === '/empresas'
            ? pathname === item.href || pathname.startsWith('/empresas/')
            : pathname === item.href;
        return (
          <Link aria-current={current ? 'page' : undefined} href={item.href} key={item.href}>
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
