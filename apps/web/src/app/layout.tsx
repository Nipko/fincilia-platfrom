import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import './globals.css';

export const metadata: Metadata = {
  title: 'Fincilia',
  description: 'Conciliacion y cierre. Entorno local con datos sinteticos.',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>
        <div className="shell">{children}</div>
        <footer className="ceiling">
          Entorno local · datos sinteticos · sin proveedores externos
        </footer>
      </body>
    </html>
  );
}
