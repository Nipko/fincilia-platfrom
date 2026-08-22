-- V0001: identidad, tenancy y autorizacion.
--
-- Company es la frontera financiera estable. Engagement es la delegacion
-- revocable de una firma sobre una company: revocarlo quita el acceso sin borrar
-- ningun hecho financiero, porque los hechos son de la company, no de la firma.
--
-- Toda tabla con `company_id` lleva RLS **forzada**. Sin `FORCE`, el propietario
-- del esquema queda exento y el aislamiento solo se sostiene mientras nadie se
-- conecte con el rol equivocado.
--
-- La politica lee `fincilia.company_id` del contexto de sesion, que el servidor
-- fija tras autorizar. Si no hay contexto, `current_setting(..., true)` devuelve
-- NULL, la comparacion es NULL y no pasa ninguna fila: falla cerrado.

CREATE SCHEMA IF NOT EXISTS fincilia AUTHORIZATION fincilia_migrator;

REVOKE CREATE ON SCHEMA fincilia FROM PUBLIC;
GRANT USAGE ON SCHEMA fincilia TO fincilia_app;

-- --------------------------------------------------------------------------- --
-- Sujetos, personas y firmas
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.subject (
  subject_id    uuid PRIMARY KEY,
  subject_kind  text NOT NULL CHECK (subject_kind IN ('person', 'service_principal')),
  display_name  text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 200),
  status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'suspended', 'deactivated')),
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- El identificador externo del proveedor de identidad se guarda tokenizado: el
-- correo es dato personal y no hace falta en claro para autorizar.
CREATE TABLE fincilia.identity_binding (
  subject_id           uuid PRIMARY KEY REFERENCES fincilia.subject(subject_id),
  issuer               text NOT NULL,
  external_subject_ref text NOT NULL,
  bound_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_identity_binding UNIQUE (issuer, external_subject_ref)
);

CREATE TABLE fincilia.firm (
  firm_id     uuid PRIMARY KEY,
  legal_name  text NOT NULL CHECK (length(legal_name) BETWEEN 1 AND 300),
  status      text NOT NULL DEFAULT 'active'
                CHECK (status IN ('active', 'suspended')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE fincilia.company (
  company_id     uuid PRIMARY KEY,
  legal_name     text NOT NULL CHECK (length(legal_name) BETWEEN 1 AND 300),
  tax_id_token   text NOT NULL,
  country_code   text NOT NULL CHECK (country_code ~ '^[A-Z]{2}$'),
  status         text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'suspended', 'archived')),
  created_at     timestamptz NOT NULL DEFAULT now(),
  -- El NIT nunca se guarda en claro: se tokeniza antes de llegar aqui.
  CONSTRAINT uq_company_tax_token UNIQUE (tax_id_token)
);

-- --------------------------------------------------------------------------- --
-- Delegacion y autorizacion
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.engagement (
  engagement_id uuid PRIMARY KEY,
  firm_id       uuid NOT NULL REFERENCES fincilia.firm(firm_id),
  company_id    uuid NOT NULL REFERENCES fincilia.company(company_id),
  status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'suspended', 'revoked')),
  valid_from    date NOT NULL,
  valid_to      date,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ck_engagement_window CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

-- Una firma no puede tener dos delegaciones activas sobre la misma company: si
-- las hubiera, revocar una dejaria el acceso abierto por la otra.
CREATE UNIQUE INDEX uq_engagement_active
  ON fincilia.engagement (firm_id, company_id)
  WHERE status = 'active';

CREATE TABLE fincilia.membership (
  membership_id uuid PRIMARY KEY,
  subject_id    uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  firm_id       uuid NOT NULL REFERENCES fincilia.firm(firm_id),
  firm_role     text NOT NULL CHECK (firm_role IN ('owner', 'firm_admin', 'member')),
  status        text NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active', 'revoked')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_membership UNIQUE (subject_id, firm_id)
);

CREATE TABLE fincilia.company_grant (
  grant_id     uuid PRIMARY KEY,
  company_id   uuid NOT NULL REFERENCES fincilia.company(company_id),
  subject_id   uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  company_role text NOT NULL
                 CHECK (company_role IN ('owner', 'firm_admin', 'preparer',
                                         'reviewer', 'auditor', 'read_only')),
  granted_by   uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  granted_at   timestamptz NOT NULL DEFAULT now(),
  revoked_at   timestamptz,
  -- Quien concede no se concede a si mismo: la separacion de funciones empieza
  -- en el otorgamiento, no solo en el flujo de aprobacion.
  CONSTRAINT ck_grant_not_self CHECK (granted_by <> subject_id),
  CONSTRAINT uq_company_grant UNIQUE (company_id, subject_id, company_role)
);

-- `authorization_version` sube en cada cambio de permisos de la company. Un
-- token emitido antes queda obsoleto sin necesidad de esperar a que expire.
CREATE TABLE fincilia.authorization_version (
  company_id uuid PRIMARY KEY REFERENCES fincilia.company(company_id),
  version    bigint NOT NULL DEFAULT 1 CHECK (version >= 1),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------------------- --
-- Auditoria append-only
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.audit_event (
  audit_event_id uuid PRIMARY KEY,
  company_id     uuid REFERENCES fincilia.company(company_id),
  subject_id     uuid REFERENCES fincilia.subject(subject_id),
  action         text NOT NULL CHECK (length(action) BETWEEN 1 AND 100),
  resource_kind  text NOT NULL,
  resource_ref   text NOT NULL,
  outcome        text NOT NULL CHECK (outcome IN ('allowed', 'denied', 'error')),
  occurred_at    timestamptz NOT NULL DEFAULT now(),
  detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- Un evento de auditoria no lleva payload crudo ni datos de negocio: guarda
  -- que paso, no que decia el fichero.
  CONSTRAINT ck_audit_detail_bounded CHECK (pg_column_size(detail) <= 4096)
);

CREATE INDEX idx_audit_company_time
  ON fincilia.audit_event (company_id, occurred_at DESC);

-- --------------------------------------------------------------------------- --
-- Row Level Security
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.company ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.company FORCE ROW LEVEL SECURITY;
CREATE POLICY company_isolation ON fincilia.company
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.engagement ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.engagement FORCE ROW LEVEL SECURITY;
CREATE POLICY engagement_isolation ON fincilia.engagement
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.company_grant ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.company_grant FORCE ROW LEVEL SECURITY;
CREATE POLICY company_grant_isolation ON fincilia.company_grant
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.authorization_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.authorization_version FORCE ROW LEVEL SECURITY;
CREATE POLICY authorization_version_isolation ON fincilia.authorization_version
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.audit_event ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.audit_event FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_event_isolation ON fincilia.audit_event
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- --------------------------------------------------------------------------- --
-- Privilegios del rol runtime
-- --------------------------------------------------------------------------- --

GRANT SELECT, INSERT, UPDATE ON
  fincilia.subject, fincilia.identity_binding, fincilia.firm, fincilia.company,
  fincilia.engagement, fincilia.membership, fincilia.company_grant,
  fincilia.authorization_version
TO fincilia_app;

-- La auditoria es append-only tambien a nivel de privilegio: el runtime puede
-- escribir y leer, nunca corregir ni borrar lo que ya quedo registrado.
GRANT SELECT, INSERT ON fincilia.audit_event TO fincilia_app;

ALTER DEFAULT PRIVILEGES FOR ROLE fincilia_migrator IN SCHEMA fincilia
  GRANT SELECT, INSERT, UPDATE ON TABLES TO fincilia_app;
ALTER DEFAULT PRIVILEGES FOR ROLE fincilia_migrator IN SCHEMA fincilia
  REVOKE ALL ON TABLES FROM PUBLIC;
