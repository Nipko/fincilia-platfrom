-- V0002: identidad local sintetica y navegacion entre empresas.
--
-- V0001 dejo dos huecos que solo aparecen al construir el primer recorrido real:
--
-- 1. Un sujeto no podia enumerar **sus propias** empresas. La politica de
--    `company_grant` solo abre por `fincilia.company_id`, y para saber que
--    contexto pedir hace falta leer antes los grants. Se anade una segunda via:
--    cada sujeto ve las concesiones cuyo `subject_id` es el suyo. No es un
--    agujero en el aislamiento; saber a que empresas tiene uno acceso no revela
--    nada de las demas, y sigue sin poder leer las concesiones ajenas.
--
-- 2. La auditoria no admitia eventos de plataforma. Un inicio de sesion ocurre
--    antes de elegir empresa, con `company_id` NULL, y `NULL = <texto>` es NULL:
--    la fila se rechazaba. Ahora un evento sin empresa pertenece a su sujeto.
--
-- Las politicas se reemplazan; V0001 no se toca. Editar una migracion aplicada
-- aplica algo distinto de lo que se reviso, y el checksum lo impide.

-- --------------------------------------------------------------------------- --
-- Credenciales locales sinteticas
-- --------------------------------------------------------------------------- --

-- Existe **solo** para el proveedor de identidad local con usuarios sinteticos.
-- Un entorno con datos reales no usa esta tabla: alli la identidad la emite un
-- proveedor externo y aqui no se guarda ningun secreto de persona real.
CREATE TABLE fincilia.local_credential (
  subject_id  uuid PRIMARY KEY REFERENCES fincilia.subject(subject_id),
  username    text NOT NULL CHECK (length(username) BETWEEN 3 AND 120),
  algorithm   text NOT NULL CHECK (algorithm = 'pbkdf2_sha256'),
  iterations  integer NOT NULL CHECK (iterations >= 200000),
  salt        text NOT NULL CHECK (salt ~ '^[0-9a-f]{32}$'),
  secret_hash text NOT NULL CHECK (secret_hash ~ '^[0-9a-f]{64}$'),
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_local_credential_username UNIQUE (username)
);

COMMENT ON TABLE fincilia.local_credential IS
  'Solo entorno local con usuarios sinteticos. No es un almacen de identidad de produccion.';

GRANT SELECT ON fincilia.local_credential TO fincilia_app;

-- --------------------------------------------------------------------------- --
-- Navegacion: un sujeto ve sus propias concesiones
-- --------------------------------------------------------------------------- --

DROP POLICY company_grant_isolation ON fincilia.company_grant;

CREATE POLICY company_grant_isolation ON fincilia.company_grant
  USING (
    company_id::text = current_setting('fincilia.company_id', true)
    OR subject_id::text = current_setting('fincilia.subject_id', true)
  )
  -- Escribir sigue exigiendo contexto de empresa: conceder un rol es un acto
  -- dentro de una empresa, nunca una operacion de navegacion.
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- --------------------------------------------------------------------------- --
-- Auditoria de eventos de plataforma
-- --------------------------------------------------------------------------- --

DROP POLICY audit_event_isolation ON fincilia.audit_event;

CREATE POLICY audit_event_isolation ON fincilia.audit_event
  USING (
    (company_id IS NOT NULL
       AND company_id::text = current_setting('fincilia.company_id', true))
    OR (company_id IS NULL
       AND subject_id::text = current_setting('fincilia.subject_id', true))
  )
  WITH CHECK (
    (company_id IS NOT NULL
       AND company_id::text = current_setting('fincilia.company_id', true))
    OR (company_id IS NULL
       AND subject_id::text = current_setting('fincilia.subject_id', true))
  );

-- Un evento de plataforma sin sujeto no pertenece a nadie y nadie podria leerlo:
-- se prohibe en el esquema en vez de dejarlo entrar y desaparecer.
ALTER TABLE fincilia.audit_event
  ADD CONSTRAINT ck_audit_scope
  CHECK (company_id IS NOT NULL OR subject_id IS NOT NULL);

CREATE INDEX idx_audit_subject_time
  ON fincilia.audit_event (subject_id, occurred_at DESC);
