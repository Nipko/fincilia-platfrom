-- --------------------------------------------------------------------------- --
-- V0009 — Onboarding, puerta de release y linaje reconstruible (FNC-P3.5)
--
-- Tres problemas que V0008 dejo abiertos, y que esta migracion cierra:
--
--   1. **Una version del motor en borrador podia publicar.** `engine_release`
--      nacia `draft` y nadie miraba su estado. Aqui se anade la constancia de
--      quien aprobo que, y un disparador que impide cambiar lo aprobado sin
--      volver a aprobarlo.
--   2. **No habia alta de cuentas ni de fuentes.** Existian las tablas y las
--      sembraba el entorno local; no habia forma de crear una cuenta, de
--      vincularla a una fuente, ni de declarar cada cuanto se espera un extracto.
--   3. **El linaje no escalaba.** Dos nodos y dos aristas por campo y por fila
--      son ocho millones de filas de grafo para un extracto de doscientas mil
--      lineas. Aqui el plan de transformacion se versiona **por columna**, no
--      por fila, y las seis etapas logicas se reconstruyen combinandolo con el
--      localizador y las referencias que las filas ya llevan.
--
-- Ninguna funcion de esta migracion es `SECURITY DEFINER`: el unico disparador
-- que hay protege una tabla que solo el migrador puede escribir, y con derechos
-- de invocador basta.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

DO $guard$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_worker')
     OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fincilia_app') THEN
    RAISE EXCEPTION 'faltan los roles de runtime; recrea el volumen local'
      USING ERRCODE = '28000';
  END IF;
END
$guard$;

-- --------------------------------------------------------------------------- --
-- 1. Constancia de aprobacion de una version del motor
-- --------------------------------------------------------------------------- --

-- Sin `company_id`, igual que `engine_release`: aprobar una version del software
-- es un acto de plataforma, no un dato de una empresa. Por eso tampoco lleva RLS.
--
-- No es la auditoria del producto y no puede serlo: `audit_event` tiene politica
-- por empresa, y una fila con `company_id` nulo no la ve nadie. Un rastro que
-- nadie puede leer no es un rastro.
CREATE TABLE fincilia.release_approval (
  approval_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  action            text NOT NULL CHECK (action IN ('approved', 'superseded', 'rejected')),
  -- Quien, en texto libre acotado. **No** es un `subject` del producto: quien
  -- aprueba una release es una persona de plataforma, no un usuario de una firma
  -- contable, y atarlo a `subject` mezclaria dos poblaciones distintas.
  actor_identity    text NOT NULL CHECK (length(actor_identity) BETWEEN 3 AND 120),
  approval_ref      text NOT NULL CHECK (length(approval_ref) BETWEEN 3 AND 200),
  rationale         text NOT NULL CHECK (length(rationale) BETWEEN 3 AND 500),
  -- Sobre que se aprobo exactamente. Si los componentes cambian despues, la
  -- aprobacion deja de cubrirlos y la API lo nota al leer.
  components_digest char(64) NOT NULL CHECK (components_digest ~ '^[0-9a-f]{64}$'),
  occurred_at       timestamptz NOT NULL DEFAULT now(),

  -- Una accion por release. Cambiar de opinion es otra release, no otra firma
  -- sobre la misma.
  CONSTRAINT uq_release_approval_action UNIQUE (release_id, action)
);

CREATE INDEX idx_release_approval_release
  ON fincilia.release_approval (release_id, occurred_at DESC);

-- `immutable_after_approval: true` en el contrato de linaje. Un CHECK no puede
-- comparar con la fila anterior, asi que lo hace un disparador: aprobado y
-- despues cambiado seria una firma sobre algo que ya no existe.
CREATE FUNCTION fincilia.engine_release_is_frozen()
RETURNS trigger
LANGUAGE plpgsql
AS $frozen$
BEGIN
  IF OLD.state = 'approved' AND (
       NEW.release_key IS DISTINCT FROM OLD.release_key
       OR NEW.components IS DISTINCT FROM OLD.components
       OR NEW.classification IS DISTINCT FROM OLD.classification
       OR NEW.canonical_schema_version IS DISTINCT FROM OLD.canonical_schema_version
       OR NEW.approval_ref IS DISTINCT FROM OLD.approval_ref) THEN
    RAISE EXCEPTION
      'an approved engine release is immutable; supersede it and approve another'
      USING ERRCODE = '23514';
  END IF;
  -- Salir de `approved` solo hacia `superseded`. Volver a borrador borraria la
  -- historia de lo que ya publico.
  IF OLD.state = 'approved' AND NEW.state NOT IN ('approved', 'superseded') THEN
    RAISE EXCEPTION 'an approved engine release only moves to superseded'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END
$frozen$;

CREATE TRIGGER engine_release_frozen
  BEFORE UPDATE ON fincilia.engine_release
  FOR EACH ROW EXECUTE FUNCTION fincilia.engine_release_is_frozen();

-- --------------------------------------------------------------------------- --
-- 2. Cuentas y fuentes: lo que faltaba para darlas de alta
-- --------------------------------------------------------------------------- --

-- La version de la clave con la que se tokenizo el identificador. Va al lado del
-- token y no dentro: rotar la clave cambia el token y **no** cambia la identidad
-- economica de la cuenta, que es la fila.
ALTER TABLE fincilia.financial_account
  ADD COLUMN identifier_key_version integer NOT NULL DEFAULT 1
    CHECK (identifier_key_version BETWEEN 1 AND 999);
ALTER TABLE fincilia.financial_account
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE fincilia.financial_account
  ADD COLUMN closed_reason text
    CHECK (closed_reason IS NULL OR length(closed_reason) BETWEEN 1 AND 200);

-- Cerrar una cuenta es una decision con motivo. Suspenderla, tambien.
ALTER TABLE fincilia.financial_account
  ADD CONSTRAINT ck_account_closed_reason
  CHECK ((status = 'active') = (closed_reason IS NULL));

-- `canonical-model` declara `purpose_code` en `data_source` y V0008 no lo trajo.
ALTER TABLE fincilia.data_source
  ADD COLUMN purpose_code text NOT NULL DEFAULT 'operational'
    CHECK (length(purpose_code) BETWEEN 3 AND 64);
ALTER TABLE fincilia.data_source
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE fincilia.data_source
  ADD COLUMN closed_reason text
    CHECK (closed_reason IS NULL OR length(closed_reason) BETWEEN 1 AND 200);

ALTER TABLE fincilia.data_source
  ADD CONSTRAINT ck_source_closed_reason
  CHECK ((status = 'active') = (closed_reason IS NULL));

-- Una fuente se relaciona con **varias** cuentas: una pasarela liquida a una
-- cuenta bancaria y concilia contra un libro contable. Incrustar
-- `financial_account_id` en `data_source` habria hecho imposible ese caso, que
-- es el normal en cuanto hay pasarelas o marketplaces.
CREATE TABLE fincilia.data_source_account (
  link_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           uuid NOT NULL REFERENCES fincilia.company(company_id),
  data_source_id       uuid NOT NULL,
  financial_account_id uuid NOT NULL,
  relation_role        text NOT NULL CHECK (relation_role IN (
                         'primary', 'settlement', 'ledger', 'supporting')),
  valid_from           date NOT NULL DEFAULT CURRENT_DATE,
  valid_to             date,
  status               text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active', 'suspended', 'closed')),
  created_by           uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_at           timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_source_account_identity UNIQUE (link_id, company_id),
  CONSTRAINT fk_source_account_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source (data_source_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_source_account_account FOREIGN KEY (financial_account_id, company_id)
    REFERENCES fincilia.financial_account (account_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_source_account_window CHECK (valid_to IS NULL OR valid_to >= valid_from)
);

-- Una sola cuenta principal viva por fuente: si hubiera dos, «contra que cuenta
-- se publica esto» dejaria de tener respuesta.
CREATE UNIQUE INDEX uq_source_account_primary
  ON fincilia.data_source_account (company_id, data_source_id)
  WHERE relation_role = 'primary' AND status = 'active';

-- Y un solo vinculo vivo por terna. Repetirlo no anade informacion.
CREATE UNIQUE INDEX uq_source_account_live
  ON fincilia.data_source_account (data_source_id, financial_account_id, relation_role)
  WHERE status = 'active';

CREATE INDEX idx_source_account_account
  ON fincilia.data_source_account (company_id, financial_account_id);

-- --------------------------------------------------------------------------- --
-- 3. Ciclos esperados y expectativas por periodo
-- --------------------------------------------------------------------------- --

-- El **calendario**: cada cuanto se espera un extracto de esta fuente, con
-- cuantos dias de plazo y de gracia, y quien responde de que llegue.
--
-- Va aparte de `source_expectation` a proposito. `canonical-model` declara esa
-- entidad con `period_start`, `period_end` y `expected_controls`: es la
-- expectativa **de un periodo concreto**, no la regla que la genera. Meter la
-- periodicidad ahi habria hecho que cada instancia repitiera la regla, y cambiar
-- la regla obligaria a reescribir la historia.
CREATE TABLE fincilia.source_cycle (
  cycle_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id             uuid NOT NULL REFERENCES fincilia.company(company_id),
  data_source_id         uuid NOT NULL,
  periodicity            text NOT NULL CHECK (periodicity IN (
                           'monthly', 'fortnightly', 'weekly', 'custom')),
  custom_days            integer CHECK (custom_days IS NULL
                           OR custom_days BETWEEN 1 AND 366),
  -- Dias despues del cierre del periodo en los que se espera el documento.
  due_day_offset         integer NOT NULL DEFAULT 5
                           CHECK (due_day_offset BETWEEN 0 AND 120),
  -- Y cuantos mas antes de llamarlo atraso.
  grace_days             integer NOT NULL DEFAULT 3
                           CHECK (grace_days BETWEEN 0 AND 120),
  responsible_subject_id uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  timezone               text NOT NULL DEFAULT 'America/Bogota'
                           CHECK (length(timezone) BETWEEN 3 AND 64),
  status                 text NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'suspended', 'closed')),
  anchor_date            date NOT NULL DEFAULT CURRENT_DATE,
  created_by             uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_cycle_identity UNIQUE (cycle_id, company_id),
  CONSTRAINT fk_cycle_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source (data_source_id, company_id) ON DELETE RESTRICT,
  -- `custom` sin numero de dias no dice nada, y un numero de dias sobre una
  -- periodicidad con nombre propio dice dos cosas a la vez.
  CONSTRAINT ck_cycle_custom CHECK ((periodicity = 'custom') = (custom_days IS NOT NULL))
);

CREATE UNIQUE INDEX uq_cycle_live
  ON fincilia.source_cycle (company_id, data_source_id)
  WHERE status = 'active';

-- La expectativa **de un periodo**, con la forma que declara `canonical-model`.
-- `due_on` y `late_after` se calculan del ciclo y se guardan: recalcularlos mas
-- tarde con otro ciclo cambiaria si algo llego tarde, y eso ya ocurrio.
CREATE TABLE fincilia.source_expectation (
  expectation_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           uuid NOT NULL REFERENCES fincilia.company(company_id),
  data_source_id       uuid NOT NULL,
  financial_account_id uuid,
  cycle_id             uuid,
  period_start         date NOT NULL,
  period_end           date NOT NULL,
  due_on               date NOT NULL,
  late_after           date NOT NULL,
  expected_controls    jsonb NOT NULL DEFAULT '{}'::jsonb,
  state                text NOT NULL DEFAULT 'pending'
                         CHECK (state IN ('pending', 'satisfied', 'late', 'waived')),
  satisfied_by         uuid,
  satisfied_at         timestamptz,
  waived_reason        text CHECK (waived_reason IS NULL
                         OR length(waived_reason) BETWEEN 1 AND 200),
  created_at           timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_expectation_identity UNIQUE (expectation_id, company_id),
  -- Un periodo, una expectativa. Generarla dos veces no crea dos deberes.
  CONSTRAINT uq_expectation_period UNIQUE (data_source_id, period_start, period_end),
  CONSTRAINT fk_expectation_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source (data_source_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_expectation_account FOREIGN KEY (financial_account_id, company_id)
    REFERENCES fincilia.financial_account (account_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_expectation_cycle FOREIGN KEY (cycle_id, company_id)
    REFERENCES fincilia.source_cycle (cycle_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_expectation_artifact FOREIGN KEY (satisfied_by, company_id)
    REFERENCES fincilia.source_artifact (artifact_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_expectation_window CHECK (period_end >= period_start),
  CONSTRAINT ck_expectation_dates CHECK (
    due_on >= period_end AND late_after >= due_on),
  CONSTRAINT ck_expectation_satisfied CHECK (
    (state = 'satisfied') = (satisfied_by IS NOT NULL AND satisfied_at IS NOT NULL)),
  CONSTRAINT ck_expectation_waived CHECK ((state = 'waived') = (waived_reason IS NOT NULL)),
  CONSTRAINT ck_expectation_controls CHECK (pg_column_size(expected_controls) <= 16384)
);

CREATE INDEX idx_expectation_due
  ON fincilia.source_expectation (company_id, state, due_on);

-- El artefacto declara de que fuente viene. Nulo para lo ya subido, porque
-- inventarle una fuente a un fichero historico seria afirmar algo que nadie dijo.
ALTER TABLE fincilia.source_artifact
  ADD COLUMN data_source_id uuid;

ALTER TABLE fincilia.source_artifact
  ADD CONSTRAINT fk_artifact_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source (data_source_id, company_id) ON DELETE RESTRICT;

CREATE INDEX idx_artifact_source
  ON fincilia.source_artifact (company_id, data_source_id, uploaded_at DESC);

-- --------------------------------------------------------------------------- --
-- 4. Plan de transformacion: el linaje que escala
-- --------------------------------------------------------------------------- --

-- Las seis etapas de `PATH-FINANCIAL-FACT` son propiedades de **la columna**, no
-- de la fila: leer la columna 3 como decimal con coma es lo mismo en la fila 7
-- que en la 90.000. Guardarlas por fila las repetiria cien mil veces sin anadir
-- una sola informacion nueva.
--
-- El plan se ata a `(version de mapeo, version del motor)`: cambiar cualquiera de
-- las dos es otro plan, y el anterior sigue existiendo para reconstruir lo que
-- ya se publico con el.
CREATE TABLE fincilia.lineage_transform_plan (
  plan_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  mapping_version_id       uuid NOT NULL,
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  plan_digest              char(64) NOT NULL CHECK (plan_digest ~ '^[0-9a-f]{64}$'),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  field_count              integer NOT NULL CHECK (field_count >= 1),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_plan_identity UNIQUE (plan_id, company_id),
  -- Un plan por par. Si la transformacion cambia, cambia el digest del mapeo o
  -- la version del motor, y por tanto es otro par y otro plan.
  CONSTRAINT uq_plan_binding UNIQUE (mapping_version_id, engine_release_id),
  CONSTRAINT fk_plan_mapping FOREIGN KEY (mapping_version_id, company_id)
    REFERENCES fincilia.column_mapping_version (mapping_version_id, company_id)
    ON DELETE RESTRICT
);

-- Una etapa logica de un campo. Seis por campo publicado, con su operacion
-- tipada y las versiones que la produjeron.
CREATE TABLE fincilia.lineage_transform_step (
  step_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           uuid NOT NULL REFERENCES fincilia.company(company_id),
  plan_id              uuid NOT NULL,
  canonical_field      text NOT NULL CHECK (length(canonical_field) BETWEEN 1 AND 64),
  step_ordinal         integer NOT NULL CHECK (step_ordinal BETWEEN 1 AND 32),
  -- Las seis etapas de `PATH-FINANCIAL-FACT`, con sus nombres del contrato.
  stage                text NOT NULL CHECK (stage IN (
                         'artifact_version', 'raw_locator', 'extracted_field',
                         'transformed_value', 'source_record_field',
                         'financial_fact_field')),
  operation            text NOT NULL CHECK (operation IN (
                         'derived_from', 'decided_using', 'included_in_snapshot',
                         'overlay_applied', 'superseded_by', 'redacted_from')),
  input_semantic_type  text NOT NULL CHECK (length(input_semantic_type) BETWEEN 1 AND 64),
  output_semantic_type text NOT NULL CHECK (length(output_semantic_type) BETWEEN 1 AND 64),
  transform_ref        text CHECK (transform_ref IS NULL
                         OR length(transform_ref) BETWEEN 1 AND 200),
  configuration_digest char(64) NOT NULL CHECK (configuration_digest ~ '^[0-9a-f]{64}$'),
  parser_version       text NOT NULL CHECK (length(parser_version) BETWEEN 1 AND 64),
  rule_version         text NOT NULL CHECK (length(rule_version) BETWEEN 1 AND 64),
  -- En que columna del fichero empieza el camino de este campo. Es lo que ata la
  -- etapa `raw_locator` a una celda concreta cuando se combina con la fila.
  source_column        integer CHECK (source_column IS NULL OR source_column >= 0),

  CONSTRAINT uq_step_identity UNIQUE (step_id, company_id),
  CONSTRAINT uq_step_position UNIQUE (plan_id, canonical_field, step_ordinal),
  CONSTRAINT uq_step_stage UNIQUE (plan_id, canonical_field, stage),
  CONSTRAINT fk_step_plan FOREIGN KEY (plan_id, company_id)
    REFERENCES fincilia.lineage_transform_plan (plan_id, company_id) ON DELETE RESTRICT,
  -- `derived_from` significa que el valor fluyo; exige nombrar la transformacion.
  CONSTRAINT ck_step_transform CHECK (
    operation NOT IN ('derived_from', 'redacted_from') OR transform_ref IS NOT NULL)
);

CREATE INDEX idx_step_plan_field
  ON fincilia.lineage_transform_step (plan_id, canonical_field, step_ordinal);

-- El dataset dice con que plan se produjo. Sin plan no hay seis etapas, y sin
-- seis etapas no se publica.
ALTER TABLE fincilia.dataset_version
  ADD COLUMN lineage_plan_id uuid;

ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT fk_dataset_plan FOREIGN KEY (lineage_plan_id, company_id)
    REFERENCES fincilia.lineage_transform_plan (plan_id, company_id) ON DELETE RESTRICT;

-- La huella de cada campo publicado, en la propia fila del movimiento. **Huellas,
-- nunca valores**: el contrato dice `raw_value_stored_in_node: false`, y un grafo
-- que copia importes se convierte en una segunda base de datos que nadie protege.
--
-- Aqui es donde el linaje deja de escalar mal: la etapa terminal de cada campo
-- deja de ser una fila de grafo y pasa a ser una clave de este documento.
ALTER TABLE fincilia.canonical_movement
  ADD COLUMN field_digests jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE fincilia.canonical_movement
  ADD CONSTRAINT ck_movement_field_digests CHECK (
    jsonb_typeof(field_digests) = 'object'
    AND pg_column_size(field_digests) <= 4096);

-- --------------------------------------------------------------------------- --
-- 5. Escala: preparacion por lotes con estado intermedio
-- --------------------------------------------------------------------------- --

-- `staging` y `cancelled` son estados nuevos. El primero existe para que un
-- dataset a medias **nunca** parezca publicado; el segundo, para abandonarlo sin
-- borrar nada: la evidencia es append-only y borrarla para limpiar seria peor
-- que dejarla marcada.
ALTER TABLE fincilia.dataset_version
  DROP CONSTRAINT IF EXISTS dataset_version_state_check;
ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT ck_dataset_state CHECK (state IN (
    'draft', 'staging', 'validated', 'published', 'rejected', 'cancelled'));

-- Un dataset en `staging` todavia no tiene validador: quien lo valida es el
-- finalizador, cuando todos los lotes han entrado.
ALTER TABLE fincilia.dataset_version DROP CONSTRAINT ck_dataset_validated;
ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT ck_dataset_validated CHECK (
    (state IN ('draft', 'staging', 'cancelled')
     AND (validated_by IS NULL) = (validated_at IS NULL))
    OR (state NOT IN ('draft', 'staging', 'cancelled')
        AND validated_by IS NOT NULL AND validated_at IS NOT NULL));

ALTER TABLE fincilia.dataset_version DROP CONSTRAINT ck_dataset_rejected;
ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT ck_dataset_rejected CHECK (
    (state IN ('rejected', 'cancelled')) = (rejected_reason IS NOT NULL));

-- Publicar exige plan de linaje. `NOT VALID` a proposito: en un volumen local
-- anterior a esta migracion hay datasets publicados sin plan, y hacerla fallar
-- por residuo de pruebas seria impedir migrar por algo que no importa. Las filas
-- nuevas si la cumplen, que es lo que protege.
ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT ck_dataset_published_has_plan
  CHECK (state <> 'published' OR lineage_plan_id IS NOT NULL) NOT VALID;

-- Cuantas filas se esperaban. Es lo que permite decir «esto esta a medias» sin
-- tener que contar la tabla de movimientos.
ALTER TABLE fincilia.dataset_version
  ADD COLUMN expected_record_count integer
    CHECK (expected_record_count IS NULL OR expected_record_count >= 0);

-- Un lote que entro. Su existencia **es** el punto de control: la fila se
-- escribe en la misma transaccion que sus movimientos, asi que si esta, el lote
-- entero esta. Reintentar salta los que ya figuran y no duplica nada.
CREATE TABLE fincilia.dataset_chunk (
  chunk_id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES fincilia.company(company_id),
  dataset_version_id uuid NOT NULL,
  chunk_ordinal      integer NOT NULL CHECK (chunk_ordinal >= 0),
  first_record       integer NOT NULL CHECK (first_record >= 1),
  last_record        integer NOT NULL CHECK (last_record >= 1),
  movement_count     integer NOT NULL CHECK (movement_count >= 0),
  rejected_count     integer NOT NULL CHECK (rejected_count >= 0),
  completed_at       timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_chunk_identity UNIQUE (chunk_id, company_id),
  CONSTRAINT uq_chunk_ordinal UNIQUE (dataset_version_id, chunk_ordinal),
  CONSTRAINT fk_chunk_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_chunk_window CHECK (last_record >= first_record)
);

CREATE INDEX idx_chunk_dataset
  ON fincilia.dataset_chunk (dataset_version_id, chunk_ordinal);

-- Lo publicado antes de que existiera el plan no puede reconstruir seis etapas.
-- Decirlo es mas honesto que dejarlo marcado `complete`: `invalidated` significa
-- exactamente esto, que el linaje existio bajo otras reglas y ya no vale.
UPDATE fincilia.dataset_version
   SET lineage_state = 'invalidated'
 WHERE lineage_plan_id IS NULL AND lineage_state = 'complete';

-- --------------------------------------------------------------------------- --
-- 6. Aislamiento
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.data_source_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.data_source_account FORCE ROW LEVEL SECURITY;
CREATE POLICY data_source_account_isolation ON fincilia.data_source_account
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.source_cycle ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.source_cycle FORCE ROW LEVEL SECURITY;
CREATE POLICY source_cycle_isolation ON fincilia.source_cycle
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.source_expectation ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.source_expectation FORCE ROW LEVEL SECURITY;
CREATE POLICY source_expectation_isolation ON fincilia.source_expectation
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.lineage_transform_plan ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.lineage_transform_plan FORCE ROW LEVEL SECURITY;
CREATE POLICY lineage_transform_plan_isolation ON fincilia.lineage_transform_plan
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.lineage_transform_step ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.lineage_transform_step FORCE ROW LEVEL SECURITY;
CREATE POLICY lineage_transform_step_isolation ON fincilia.lineage_transform_step
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.dataset_chunk ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.dataset_chunk FORCE ROW LEVEL SECURITY;
CREATE POLICY dataset_chunk_isolation ON fincilia.dataset_chunk
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- --------------------------------------------------------------------------- --
-- 7. Privilegios
-- --------------------------------------------------------------------------- --

-- La constancia de aprobacion se lee para comprobar que lo aprobado es lo que
-- corre. **Escribirla no es cosa del runtime**: aprobar una version del motor lo
-- hace una persona con la herramienta administrativa, que corre como migrador.
GRANT SELECT ON fincilia.release_approval TO fincilia_app;

GRANT SELECT, INSERT, UPDATE ON fincilia.data_source_account TO fincilia_app;
GRANT SELECT, INSERT, UPDATE ON fincilia.source_cycle TO fincilia_app;
GRANT SELECT, INSERT, UPDATE ON fincilia.source_expectation TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.lineage_transform_plan TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.lineage_transform_step TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.dataset_chunk TO fincilia_app;

-- El plan de transformacion es evidencia de como se leyo algo: se anade, no se
-- reescribe. Corregirlo es otro plan, atado a otra version de mapeo o de motor.
REVOKE UPDATE, DELETE ON fincilia.lineage_transform_plan FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.lineage_transform_step FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.dataset_chunk FROM fincilia_app;
REVOKE DELETE ON fincilia.data_source_account FROM fincilia_app;
REVOKE DELETE ON fincilia.source_cycle FROM fincilia_app;
REVOKE DELETE ON fincilia.source_expectation FROM fincilia_app;

-- El worker extrae filas. No da de alta cuentas, no vincula fuentes, no aprueba
-- versiones del motor y no escribe linaje.
REVOKE ALL PRIVILEGES ON fincilia.release_approval FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.data_source_account FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.source_cycle FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.source_expectation FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.lineage_transform_plan FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.lineage_transform_step FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.dataset_chunk FROM fincilia_worker;
