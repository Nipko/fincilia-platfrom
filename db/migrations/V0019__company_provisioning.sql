-- V0019: aprovisionamiento transaccional de empresas desde el producto.
--
-- Company no pertenece a una firma. La relacion nace en engagement y el acceso
-- en un grant individual. Esta migracion agrega solo el control necesario para
-- crear esa cadena de forma repetible sin depender de la semilla local.

-- Autoridad tecnica que concede el primer rol. No tiene credencial, membership
-- ni grant y por tanto no puede iniciar sesion ni operar una empresa. Su unica
-- funcion es que el propietario inicial no figure concediendose acceso a si
-- mismo, lo cual conserva ck_grant_not_self.
INSERT INTO fincilia.subject (
  subject_id, subject_kind, display_name, status
) VALUES (
  '4d1d048f-07af-5ccd-bd76-abace2124b63',
  'service_principal',
  'Fincilia Provisioning Authority',
  'active'
) ON CONFLICT (subject_id) DO NOTHING;

ALTER TABLE fincilia.company
  ADD COLUMN tax_id_key_version smallint NOT NULL DEFAULT 1
    CHECK (tax_id_key_version BETWEEN 1 AND 999);

-- El modelo permite muchos engagements historicos o consultivos, pero como
-- maximo un operador contable primario activo por empresa. La unicidad parcial
-- hace atomica la regla incluso con dos altas concurrentes.
ALTER TABLE fincilia.engagement
  ADD COLUMN is_primary_operator boolean NOT NULL DEFAULT false;

CREATE UNIQUE INDEX uq_engagement_primary_operator
  ON fincilia.engagement (company_id)
  WHERE status = 'active' AND is_primary_operator;

-- Recibo de idempotencia de plataforma. No contiene NIT, identificadores de
-- cuenta, nombres ni importes: solo huella de solicitud e IDs generados. Su
-- frontera es el sujeto autenticado, porque antes de crear la company aun no
-- existe un contexto financiero que pueda protegerla.
CREATE TABLE fincilia.company_provisioning_command (
  command_id       uuid PRIMARY KEY,
  subject_id       uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  firm_id          uuid NOT NULL REFERENCES fincilia.firm(firm_id),
  idempotency_key  text NOT NULL CHECK (length(idempotency_key) BETWEEN 16 AND 128),
  request_digest   text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
  state            text NOT NULL DEFAULT 'running'
                     CHECK (state IN ('running', 'completed')),
  company_id       uuid REFERENCES fincilia.company(company_id),
  result           jsonb CHECK (result IS NULL OR pg_column_size(result) <= 4096),
  created_at       timestamptz NOT NULL DEFAULT now(),
  completed_at     timestamptz,
  CONSTRAINT uq_company_provisioning_subject_key
    UNIQUE (subject_id, idempotency_key),
  CONSTRAINT ck_company_provisioning_completion
    CHECK (
      (state = 'running' AND company_id IS NULL AND result IS NULL
                         AND completed_at IS NULL)
      OR
      (state = 'completed' AND company_id IS NOT NULL AND result IS NOT NULL
                           AND completed_at IS NOT NULL)
    )
);

ALTER TABLE fincilia.company_provisioning_command ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.company_provisioning_command FORCE ROW LEVEL SECURITY;

CREATE POLICY company_provisioning_subject_isolation
  ON fincilia.company_provisioning_command
  USING (subject_id::text = current_setting('fincilia.subject_id', true))
  WITH CHECK (subject_id::text = current_setting('fincilia.subject_id', true));

REVOKE ALL ON fincilia.company_provisioning_command FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE ON fincilia.company_provisioning_command TO fincilia_app;

COMMENT ON TABLE fincilia.company_provisioning_command IS
  'Recibos idempotentes sin payload para alta de company; aislados por subject.';
