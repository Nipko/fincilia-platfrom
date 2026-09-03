import Link from 'next/link';

import { managedOidcRegistrationEnabled } from '@/lib/managed-oidc';
import { readSession } from '@/lib/session';

export default async function Home() {
  const session = await readSession();
  const googleRegistration = managedOidcRegistrationEnabled();
  return (
    <main className="public-home">
      <section className="public-hero">
        <div className="public-hero__copy">
          <p className="eyebrow">Conciliación clara para equipos contables</p>
          <h1>De documentos dispersos a diferencias explicables.</h1>
          <p>
            Fincilia organiza, limpia y coteja información financiera con un rastro
            visible desde la celda de origen hasta la revisión humana.
          </p>
          <div className="public-actions">
            <Link className="primary-link" href={session ? '/empresas' : '/registro'}>
              {session ? 'Ir a mi portafolio' : 'Crear mi cuenta'}
            </Link>
            <Link className="secondary-link" href="/entrar">Entrar</Link>
          </div>
          <p className="public-stage-note">
            {googleRegistration
              ? 'Registro público con Google · datos reales pendientes de autorización.'
              : 'Entorno UAT · identidad administrada pendiente de activación.'}
          </p>
        </div>
        <div className="public-hero__visual card" aria-label="Flujo de Fincilia">
          <div><span>01</span><strong>Carga</strong><small>Excel, CSV y evidencia</small></div>
          <div><span>02</span><strong>Limpia</strong><small>Tipos, columnas y calidad</small></div>
          <div><span>03</span><strong>Concilia</strong><small>Propuestas y revisión humana</small></div>
          <div><span>04</span><strong>Explica</strong><small>Linaje, diferencias e informes</small></div>
        </div>
      </section>

      <section className="public-section" aria-labelledby="public-capabilities">
        <p className="eyebrow">Una plataforma, varios cierres</p>
        <h2 id="public-capabilities">Pensada para contadores y PYMEs</h2>
        <div className="public-grid">
          <article className="card"><strong>Portafolio multiempresa</strong><p>Ciclos, pendientes, volúmenes y equipos en una vista.</p></article>
          <article className="card"><strong>Limpieza visual</strong><p>Reconoce hojas, filas, columnas y tipos antes de publicar.</p></article>
          <article className="card"><strong>Conciliación revisable</strong><p>Candidatos 1:1 y agrupados, siempre con decisión humana.</p></article>
          <article className="card"><strong>Seguridad por diseño</strong><p>RLS por empresa, roles, auditoría y evidencia reproducible.</p></article>
        </div>
      </section>

      <section className="public-trust card">
        <div><p className="eyebrow">Construido con trazabilidad</p><h2>Privacidad visible desde el inicio.</h2></div>
        <div>
          <p>
            Conoce qué tratamos, qué no hacemos y cómo se elimina una cuenta antes
            de registrarte. Fincilia es desarrollado por{' '}
            <a href="https://parallext.com" rel="noreferrer" target="_blank">Parallext.com</a>.
          </p>
          <p>
            Al habilitar el acceso con Google, Fincilia usará únicamente el
            identificador, nombre y correo verificado para autenticar tu cuenta.
            No pedirá acceso a Gmail, Drive, contactos ni calendario.
          </p>
        </div>
        <Link href="/privacy">Leer política de privacidad</Link>
      </section>
    </main>
  );
}
