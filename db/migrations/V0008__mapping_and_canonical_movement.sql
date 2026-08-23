-- --------------------------------------------------------------------------- --
-- V0008 — Mapeo y movimiento canonico (FNC-P3)
--
-- Lo que esta migracion persiste es la cadena completa que va de unos bytes
-- aceptados hasta un importe publicado, y la deja auditable en cada eslabon:
--
--   source_artifact -> raw_record -> source_record -> canonical_movement
--                          |             |                  |
--                          +-------- lineage_node/lineage_edge --------+
--
-- Tres decisiones la gobiernan, y las tres estan tomadas fuera de este fichero:
--
--   1. `financial_account` es una entidad de primera clase. `canonical-model`
--      declara `money_movement.financial_account_id` no nulo y la entidad no
--      existia: un movimiento no podia satisfacer su propio contrato.
--   2. `engine_release` es persistente y versionado. Ningun dataset publicado
--      referencia `latest`; hay un CHECK que rechaza los tokens flotantes.
--   3. Publicar un dataset es `dataset.publish`, un permiso propio, y quien
--      publica no puede ser quien preparo la version. Eso no se deja al
--      codigo: es un CHECK.
--
-- Nada aqui reintroduce auto-match, conciliacion ni cierre.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- Los roles los crea el bootstrap sobre un volumen vacio. Si faltan, esta
-- migracion se detiene diciendolo: conceder privilegios a medias es peor que
-- no conceder ninguno.
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
-- Version del motor
-- --------------------------------------------------------------------------- --

-- Sin `company_id` a proposito: una version del software no es dato de una
-- empresa. Por eso no lleva RLS —no hay nada que aislar— y por eso el runtime
-- solo tiene SELECT.
--
-- `state` arranca en `draft` y solo una persona lo aprueba: el contrato de
-- linaje dice `agent_can_self_approve: false`. Esta migracion no aprueba nada.
CREATE TABLE fincilia.engine_release (
  release_id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  release_key              text NOT NULL UNIQUE
                             CHECK (length(release_key) BETWEEN 3 AND 120),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  classification           text NOT NULL CHECK (classification IN ('neutral', 'affects_results')),
  state                    text NOT NULL DEFAULT 'draft'
                             CHECK (state IN ('draft', 'approved', 'superseded')),
  approval_ref             text CHECK (approval_ref IS NULL OR length(approval_ref) BETWEEN 1 AND 200),
  components               jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at               timestamptz NOT NULL DEFAULT now(),

  -- Reproducir exige nombrar. `latest` no nombra nada: manana apunta a otro
  -- binario y el mismo manifiesto produce otro resultado.
  CONSTRAINT ck_release_not_floating CHECK (
    lower(release_key) NOT IN ('latest', 'main', 'head', 'stable', 'current')),
  -- Aprobado y sin referencia de aprobacion seria una firma sin firmante.
  CONSTRAINT ck_release_approval CHECK ((state = 'approved') = (approval_ref IS NOT NULL)),
  CONSTRAINT ck_release_components CHECK (
    jsonb_typeof(components) = 'array' AND pg_column_size(components) <= 16384)
);

-- --------------------------------------------------------------------------- --
-- Maestros de empresa
-- --------------------------------------------------------------------------- --

-- La cuenta contra la que ocurre el movimiento. `identifier_token` es un token,
-- no el numero: `canonical-model` lo tipa como `tokenized_identifier`, y los
-- cuatro ultimos digitos van aparte porque son lo unico que una persona
-- necesita ver para reconocer la cuenta.
CREATE TABLE fincilia.financial_account (
  account_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        uuid NOT NULL REFERENCES fincilia.company(company_id),
  account_family    text NOT NULL CHECK (account_family IN (
                      'bank_account', 'payment_gateway', 'merchant_acquirer',
                      'marketplace', 'digital_wallet', 'billing_erp',
                      'accounting_ledger')),
  display_name      text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 160),
  identifier_token  text NOT NULL CHECK (length(identifier_token) BETWEEN 8 AND 128),
  identifier_last4  text CHECK (identifier_last4 ~ '^[0-9]{4}$'),
  currency_code     text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  timezone          text NOT NULL DEFAULT 'America/Bogota'
                      CHECK (length(timezone) BETWEEN 3 AND 64),
  status            text NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active', 'suspended', 'closed')),
  created_at        timestamptz NOT NULL DEFAULT now(),

  -- Objetivo de las claves foraneas compuestas: sin este UNIQUE, una fila de
  -- otra empresa podria referenciarse por su solo identificador.
  CONSTRAINT uq_account_identity UNIQUE (account_id, company_id),
  CONSTRAINT uq_account_token UNIQUE (company_id, account_family, identifier_token)
);

-- De donde viene la evidencia. `artifact_version.data_source_id` y
-- `source_record.data_source_id` lo exigen no nulo.
CREATE TABLE fincilia.data_source (
  data_source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id     uuid NOT NULL REFERENCES fincilia.company(company_id),
  source_family  text NOT NULL CHECK (source_family IN (
                   'bank_account', 'payment_gateway', 'merchant_acquirer',
                   'marketplace', 'digital_wallet', 'billing_erp',
                   'accounting_ledger', 'tax_documents_received',
                   'supporting_evidence', 'reference_data')),
  display_name   text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 160),
  timezone       text NOT NULL DEFAULT 'America/Bogota'
                   CHECK (length(timezone) BETWEEN 3 AND 64),
  status         text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'suspended', 'closed')),
  created_at     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_data_source_identity UNIQUE (data_source_id, company_id),
  CONSTRAINT uq_data_source_name UNIQUE (company_id, display_name)
);

-- El artefacto ya existia (V0003) sin identidad compuesta. Se la damos aqui
-- para que raw_record no pueda apuntar al fichero de otra empresa.
ALTER TABLE fincilia.source_artifact
  ADD CONSTRAINT uq_artifact_identity UNIQUE (artifact_id, company_id);

-- --------------------------------------------------------------------------- --
-- Mapeo
-- --------------------------------------------------------------------------- --

-- La plantilla estable. Lo que cambia —y por tanto lo que se versiona— vive en
-- `column_mapping_version`.
CREATE TABLE fincilia.column_mapping (
  mapping_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id     uuid NOT NULL REFERENCES fincilia.company(company_id),
  data_source_id uuid NOT NULL,
  display_name   text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 160),
  created_by     uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_at     timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_mapping_identity UNIQUE (mapping_id, company_id),
  CONSTRAINT uq_mapping_name UNIQUE (company_id, display_name),
  CONSTRAINT fk_mapping_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source (data_source_id, company_id) ON DELETE RESTRICT
);

-- Una version de mapeo es inmutable en lo que decide. `state` avanza
-- `draft -> validated`, y la publicacion del dataset la sella.
-- El cuerpo (`definition`) no cambia despues de `validated`: si cambia, es otra
-- version, y por eso el dataset publicado la referencia por identificador.
CREATE TABLE fincilia.column_mapping_version (
  mapping_version_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id           uuid NOT NULL REFERENCES fincilia.company(company_id),
  mapping_id           uuid NOT NULL,
  version_number       integer NOT NULL CHECK (version_number >= 1),
  artifact_id          uuid NOT NULL,
  definition           jsonb NOT NULL,
  definition_digest    char(64) NOT NULL CHECK (definition_digest ~ '^[0-9a-f]{64}$'),
  source_schema_digest char(64) NOT NULL CHECK (source_schema_digest ~ '^[0-9a-f]{64}$'),
  state                text NOT NULL DEFAULT 'draft'
                         CHECK (state IN ('draft', 'validated', 'superseded')),
  created_by           uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  created_at           timestamptz NOT NULL DEFAULT now(),
  validated_by         uuid REFERENCES fincilia.subject(subject_id),
  validated_at         timestamptz,

  CONSTRAINT uq_mapping_version_identity UNIQUE (mapping_version_id, company_id),
  CONSTRAINT uq_mapping_version_number UNIQUE (mapping_id, version_number),
  CONSTRAINT fk_mapping_version_mapping FOREIGN KEY (mapping_id, company_id)
    REFERENCES fincilia.column_mapping (mapping_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_mapping_version_artifact FOREIGN KEY (artifact_id, company_id)
    REFERENCES fincilia.source_artifact (artifact_id, company_id) ON DELETE RESTRICT,
  -- Validado sin validador ni marca de tiempo seria un estado sin hecho detras.
  CONSTRAINT ck_mapping_version_validated CHECK (
    (state = 'draft' AND validated_by IS NULL AND validated_at IS NULL)
    OR (state <> 'draft' AND validated_by IS NOT NULL AND validated_at IS NOT NULL)),
  CONSTRAINT ck_mapping_version_bounded CHECK (pg_column_size(definition) <= 65536)
);

-- Cada ambiguedad que una persona resolvio, con su motivo. El perfilador marca
-- `ambiguous_date` y `ambiguous_numeric`; mientras quede una sin fila aqui, la
-- publicacion se bloquea.
--
-- `resolved_value` es una eleccion de convenio —`dmy`, `comma`, `outflow`—,
-- nunca un valor del fichero: esta tabla no es un sitio donde guardar datos.
CREATE TABLE fincilia.mapping_decision (
  decision_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id         uuid NOT NULL REFERENCES fincilia.company(company_id),
  mapping_version_id uuid NOT NULL,
  ambiguity_kind     text NOT NULL CHECK (ambiguity_kind IN (
                       'date_format', 'decimal_format', 'direction_sign',
                       'currency', 'column_role', 'timezone')),
  subject_ref        text NOT NULL CHECK (length(subject_ref) BETWEEN 1 AND 120),
  resolved_value     text NOT NULL CHECK (length(resolved_value) BETWEEN 1 AND 64),
  rationale          text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 500),
  decided_by         uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  decided_at         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_decision_identity UNIQUE (decision_id, company_id),
  -- Una ambiguedad, una decision vigente. Cambiar de opinion es una version
  -- de mapeo nueva, no una reescritura de esta fila.
  CONSTRAINT uq_decision_subject UNIQUE (mapping_version_id, ambiguity_kind, subject_ref),
  CONSTRAINT fk_decision_version FOREIGN KEY (mapping_version_id, company_id)
    REFERENCES fincilia.column_mapping_version (mapping_version_id, company_id)
    ON DELETE RESTRICT
);

-- --------------------------------------------------------------------------- --
-- Dataset publicado
-- --------------------------------------------------------------------------- --

-- La unidad de publicacion. Nace `draft`, pasa a `validated` cuando el
-- preparador comprueba que no queda ambiguedad, y a `published` cuando otro
-- sujeto con `dataset.publish` la sella.
--
-- Publicar dos veces la misma terna (run, version de mapeo, release) no duplica
-- nada: `uq_dataset_reproduction` lo impide en el motor, no en el codigo.
CREATE TABLE fincilia.dataset_version (
  dataset_version_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  processing_run_id        uuid NOT NULL,
  mapping_version_id       uuid NOT NULL,
  artifact_id              uuid NOT NULL,
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  revision                 integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
  state                    text NOT NULL DEFAULT 'draft'
                             CHECK (state IN ('draft', 'validated', 'published', 'rejected')),
  completeness_state       text NOT NULL DEFAULT 'unknown'
                             CHECK (completeness_state IN (
                               'verified', 'mismatch', 'unknown', 'accepted_exception')),
  lineage_state            text NOT NULL DEFAULT 'required_pending'
                             CHECK (lineage_state IN ('required_pending', 'complete', 'invalidated')),
  record_count             integer NOT NULL DEFAULT 0 CHECK (record_count >= 0),
  movement_count           integer NOT NULL DEFAULT 0 CHECK (movement_count >= 0),
  rejected_count           integer NOT NULL DEFAULT 0 CHECK (rejected_count >= 0),
  prepared_by              uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  prepared_at              timestamptz NOT NULL DEFAULT now(),
  validated_by             uuid REFERENCES fincilia.subject(subject_id),
  validated_at             timestamptz,
  published_by             uuid REFERENCES fincilia.subject(subject_id),
  published_at             timestamptz,
  rejected_reason          text CHECK (rejected_reason IS NULL OR length(rejected_reason) BETWEEN 1 AND 200),

  CONSTRAINT uq_dataset_identity UNIQUE (dataset_version_id, company_id),
  -- Idempotencia de publicacion: dataset + version de mapeo + release.
  CONSTRAINT uq_dataset_reproduction UNIQUE (
    company_id, processing_run_id, mapping_version_id, engine_release_id),
  CONSTRAINT fk_dataset_run FOREIGN KEY (processing_run_id, company_id)
    REFERENCES fincilia.processing_run (run_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_dataset_mapping_version FOREIGN KEY (mapping_version_id, company_id)
    REFERENCES fincilia.column_mapping_version (mapping_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_dataset_artifact FOREIGN KEY (artifact_id, company_id)
    REFERENCES fincilia.source_artifact (artifact_id, company_id) ON DELETE RESTRICT,
  -- Segregacion de funciones, en el motor. Quien preparo la version no la
  -- publica, tenga el rol que tenga. Un owner acumula ambos permisos; lo que
  -- no puede es ejercerlos sobre esta fila.
  CONSTRAINT ck_dataset_publisher_is_not_author CHECK (
    published_by IS NULL OR published_by <> prepared_by),
  CONSTRAINT ck_dataset_validated CHECK (
    (state = 'draft' AND validated_by IS NULL AND validated_at IS NULL)
    OR (state <> 'draft' AND validated_by IS NOT NULL AND validated_at IS NOT NULL)),
  CONSTRAINT ck_dataset_published CHECK (
    (state = 'published') = (published_by IS NOT NULL AND published_at IS NOT NULL)),
  CONSTRAINT ck_dataset_rejected CHECK ((state = 'rejected') = (rejected_reason IS NOT NULL))
);

-- El manifiesto que hace reproducible al dataset. `reproduction_key` es el
-- sha256 del JSON canonico de todo lo que entra, sin los digests de salida:
-- dos ejecuciones con la misma clave deben producir los mismos bytes, o
-- fallar diciendolo.
CREATE TABLE fincilia.reproducibility_manifest (
  manifest_id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id              uuid NOT NULL REFERENCES fincilia.company(company_id),
  dataset_version_id      uuid NOT NULL,
  engine_release_id       uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  input_artifact_sha256   char(64) NOT NULL CHECK (input_artifact_sha256 ~ '^[0-9a-f]{64}$'),
  mapping_version_id      uuid NOT NULL,
  deterministic_config    jsonb NOT NULL,
  locale                  text NOT NULL CHECK (length(locale) BETWEEN 2 AND 16),
  timezone                text NOT NULL CHECK (length(timezone) BETWEEN 3 AND 64),
  random_seed             bigint NOT NULL DEFAULT 0,
  output_digests          jsonb NOT NULL DEFAULT '{}'::jsonb,
  reproduction_key        char(64) NOT NULL CHECK (reproduction_key ~ '^[0-9a-f]{64}$'),
  reproducible            boolean NOT NULL DEFAULT true,
  not_reproducible_reason text CHECK (
    not_reproducible_reason IS NULL OR length(not_reproducible_reason) BETWEEN 1 AND 200),
  created_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_manifest_identity UNIQUE (manifest_id, company_id),
  CONSTRAINT uq_manifest_dataset UNIQUE (dataset_version_id),
  CONSTRAINT fk_manifest_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_manifest_mapping_version FOREIGN KEY (mapping_version_id, company_id)
    REFERENCES fincilia.column_mapping_version (mapping_version_id, company_id)
    ON DELETE RESTRICT,
  -- No reproducible sin motivo escrito seria una excusa, no un hecho.
  CONSTRAINT ck_manifest_reason CHECK (reproducible = (not_reproducible_reason IS NULL)),
  CONSTRAINT ck_manifest_bounded CHECK (
    pg_column_size(deterministic_config) <= 16384
    AND pg_column_size(output_digests) <= 16384)
);

-- --------------------------------------------------------------------------- --
-- Evidencia extraida
-- --------------------------------------------------------------------------- --

-- Una fila del fichero, tal cual se leyo. `origin_locator` es la coordenada
-- exacta dentro de la version del artefacto: sin ella no hay drill-down, y el
-- contrato de linaje prohibe el localizador opaco universal.
CREATE TABLE fincilia.raw_record (
  raw_record_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id        uuid NOT NULL REFERENCES fincilia.company(company_id),
  artifact_id       uuid NOT NULL,
  processing_run_id uuid NOT NULL,
  record_ordinal    integer NOT NULL CHECK (record_ordinal >= 1),
  origin_locator    jsonb NOT NULL,
  raw_values        jsonb NOT NULL,
  values_digest     char(64) NOT NULL CHECK (values_digest ~ '^[0-9a-f]{64}$'),
  created_at        timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_raw_record_identity UNIQUE (raw_record_id, company_id),
  -- Una fila del fichero, una vez por ejecucion. Reprocesar crea otra
  -- ejecucion, no sobrescribe esta.
  CONSTRAINT uq_raw_record_ordinal UNIQUE (processing_run_id, record_ordinal),
  CONSTRAINT fk_raw_record_artifact FOREIGN KEY (artifact_id, company_id)
    REFERENCES fincilia.source_artifact (artifact_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_raw_record_run FOREIGN KEY (processing_run_id, company_id)
    REFERENCES fincilia.processing_run (run_id, company_id) ON DELETE RESTRICT,
  -- Las cuatro coordenadas que exige `tabular_delimited`. Un localizador sin
  -- span de bytes no permite volver al fichero y comprobar.
  CONSTRAINT ck_raw_locator_typed CHECK (
    origin_locator ? 'locator_kind'
    AND origin_locator ? 'artifact_sha256'
    AND origin_locator ? 'record_ordinal'
    AND origin_locator ? 'byte_start'
    AND origin_locator ? 'byte_end'
    AND origin_locator ? 'field_count'),
  CONSTRAINT ck_raw_locator_bounds CHECK (
    (origin_locator ->> 'byte_start')::bigint >= 0
    AND (origin_locator ->> 'byte_end')::bigint > (origin_locator ->> 'byte_start')::bigint
    AND (origin_locator ->> 'field_count')::integer >= 1),
  CONSTRAINT ck_raw_values_shape CHECK (
    jsonb_typeof(raw_values) = 'array' AND pg_column_size(raw_values) <= 65536),
  CONSTRAINT ck_raw_locator_bounded CHECK (pg_column_size(origin_locator) <= 4096)
);

CREATE INDEX idx_raw_record_run ON fincilia.raw_record (processing_run_id, record_ordinal);

-- La fila ya tipada, todavia sin interpretar como movimiento. Es el eslabon
-- que el contrato de linaje llama `source_record_field`.
CREATE TABLE fincilia.source_record (
  source_record_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  dataset_version_id       uuid NOT NULL,
  data_source_id           uuid NOT NULL,
  raw_record_id            uuid NOT NULL,
  record_family            text NOT NULL CHECK (length(record_family) BETWEEN 1 AND 64),
  provider_event_id        text CHECK (provider_event_id IS NULL
                             OR length(provider_event_id) BETWEEN 1 AND 200),
  source_payload           jsonb NOT NULL,
  state                    text NOT NULL DEFAULT 'draft'
                             CHECK (state IN ('draft', 'published', 'superseded', 'rejected')),
  rejection_code           text CHECK (rejection_code IS NULL
                             OR length(rejection_code) BETWEEN 1 AND 64),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state            text NOT NULL DEFAULT 'required_pending'
                             CHECK (lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_source_record_identity UNIQUE (source_record_id, company_id),
  CONSTRAINT uq_source_record_raw UNIQUE (dataset_version_id, raw_record_id),
  CONSTRAINT fk_source_record_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_source_record_source FOREIGN KEY (data_source_id, company_id)
    REFERENCES fincilia.data_source (data_source_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_source_record_raw FOREIGN KEY (raw_record_id, company_id)
    REFERENCES fincilia.raw_record (raw_record_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT ck_source_record_rejection CHECK ((state = 'rejected') = (rejection_code IS NOT NULL)),
  CONSTRAINT ck_source_payload_bounded CHECK (pg_column_size(source_payload) <= 65536)
);

CREATE INDEX idx_source_record_dataset ON fincilia.source_record (dataset_version_id);

-- --------------------------------------------------------------------------- --
-- Movimiento canonico
-- --------------------------------------------------------------------------- --

-- El hecho economico. Inmutable para el runtime: `GRANT SELECT, INSERT` y
-- `REVOKE UPDATE, DELETE`, igual que `source_artifact`. Corregir un movimiento
-- publicado es publicar otra version del dataset, nunca reescribir esta fila.
--
-- Tres cosas que este esquema se niega a hacer:
--
--   * inferir la direccion del signo del importe. `amount` es siempre positivo
--     —`canonical-model` lo tipa `value_rule: positive`— y `direction` va
--     aparte, decidida en el mapeo y auditada;
--   * tratar la referencia del proveedor como unicidad economica. Dos cobros
--     legitimos identicos existen, y colapsarlos seria perder dinero de vista.
--     Hay indice, no UNIQUE;
--   * confundir cuando ocurrio, cuando se asento y a que periodo contable
--     pertenece. Son tres fechas distintas y se guardan como tres columnas.
CREATE TABLE fincilia.canonical_movement (
  movement_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  dataset_version_id       uuid NOT NULL,
  source_record_id         uuid NOT NULL,
  financial_account_id     uuid NOT NULL,
  kind                     text NOT NULL DEFAULT 'other' CHECK (kind IN (
                             'payment', 'payout', 'refund', 'chargeback', 'fee',
                             'tax', 'withholding', 'transfer', 'adjustment', 'other')),
  amount                   numeric(38, 12) NOT NULL CHECK (amount > 0),
  currency_code            text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  direction                text NOT NULL CHECK (direction IN ('inflow', 'outflow')),
  description              text NOT NULL CHECK (length(description) BETWEEN 1 AND 500),
  reference_original       text CHECK (reference_original IS NULL
                             OR length(reference_original) BETWEEN 1 AND 200),
  reference_normalised     text CHECK (reference_normalised IS NULL
                             OR length(reference_normalised) BETWEEN 1 AND 200),
  occurred_on              date NOT NULL,
  posted_on                date,
  value_date               date,
  accounting_date          date,
  dedupe_fingerprint       char(64) NOT NULL CHECK (dedupe_fingerprint ~ '^[0-9a-f]{64}$'),
  state                    text NOT NULL DEFAULT 'proposed'
                             CHECK (state IN ('proposed', 'confirmed', 'reversed', 'voided')),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state            text NOT NULL DEFAULT 'required_pending'
                             CHECK (lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_movement_identity UNIQUE (movement_id, company_id),
  -- Un registro de origen produce un movimiento dentro de un dataset. Repetir
  -- la publicacion no duplica; reprocesar crea otro dataset y otro movimiento,
  -- y el anterior se conserva.
  CONSTRAINT uq_movement_origin UNIQUE (dataset_version_id, source_record_id),
  CONSTRAINT fk_movement_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_movement_source_record FOREIGN KEY (source_record_id, company_id)
    REFERENCES fincilia.source_record (source_record_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_movement_account FOREIGN KEY (financial_account_id, company_id)
    REFERENCES fincilia.financial_account (account_id, company_id) ON DELETE RESTRICT,
  -- Las fechas derivadas no pueden ser anteriores a la ocurrencia.
  CONSTRAINT ck_movement_dates CHECK (
    (posted_on IS NULL OR posted_on >= occurred_on)
    AND (value_date IS NULL OR value_date >= occurred_on)),
  CONSTRAINT ck_movement_reference_pairing CHECK (
    (reference_original IS NULL) = (reference_normalised IS NULL))
);

-- Indice, no restriccion: buscar por referencia es util, imponerla como
-- identidad es un error contable.
CREATE INDEX idx_movement_reference
  ON fincilia.canonical_movement (company_id, reference_normalised)
  WHERE reference_normalised IS NOT NULL;
CREATE INDEX idx_movement_dataset ON fincilia.canonical_movement (dataset_version_id);
CREATE INDEX idx_movement_account_date
  ON fincilia.canonical_movement (company_id, financial_account_id, occurred_on DESC);
CREATE INDEX idx_movement_fingerprint
  ON fincilia.canonical_movement (company_id, dedupe_fingerprint);

-- Que evidencia sostiene que movimiento, y con cuanto. Append-only.
CREATE TABLE fincilia.movement_evidence_link (
  link_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  movement_id              uuid NOT NULL,
  source_record_id         uuid NOT NULL,
  link_role                text NOT NULL CHECK (link_role IN (
                             'origin', 'supporting', 'correction')),
  allocated_amount         numeric(38, 12) NOT NULL CHECK (allocated_amount > 0),
  currency_code            text NOT NULL CHECK (currency_code ~ '^[A-Z]{3}$'),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  lineage_state            text NOT NULL DEFAULT 'required_pending'
                             CHECK (lineage_state IN ('required_pending', 'complete', 'invalidated')),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_link_identity UNIQUE (link_id, company_id),
  CONSTRAINT uq_link_pair UNIQUE (movement_id, source_record_id, link_role),
  CONSTRAINT fk_link_movement FOREIGN KEY (movement_id, company_id)
    REFERENCES fincilia.canonical_movement (movement_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_link_source_record FOREIGN KEY (source_record_id, company_id)
    REFERENCES fincilia.source_record (source_record_id, company_id) ON DELETE RESTRICT
);

-- --------------------------------------------------------------------------- --
-- Linaje
-- --------------------------------------------------------------------------- --

-- Un nodo del grafo. `value_digest` y nunca el valor: el contrato dice
-- `raw_value_stored_in_node: false`, y un grafo de linaje que copia importes
-- se convierte en una segunda base de datos que nadie protege.
CREATE TABLE fincilia.lineage_node (
  node_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  node_type                text NOT NULL CHECK (node_type IN (
                             'artifact_version', 'raw_locator', 'extracted_field',
                             'transformed_value', 'source_record_field',
                             'financial_fact_field', 'decision')),
  entity_ref               uuid NOT NULL,
  field_name               text NOT NULL DEFAULT ''
                             CHECK (length(field_name) BETWEEN 0 AND 64),
  locator                  jsonb,
  value_digest             char(64) CHECK (value_digest IS NULL OR value_digest ~ '^[0-9a-f]{64}$'),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  created_at               timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_lineage_node_identity UNIQUE (node_id, company_id),
  -- `field_name` no admite NULL a proposito: en un UNIQUE, dos NULL no chocan,
  -- y el nodo de artefacto se duplicaria en silencio.
  CONSTRAINT uq_lineage_node_natural UNIQUE (company_id, node_type, entity_ref, field_name),
  -- Un nodo de celda sin coordenada no permite volver al fichero.
  CONSTRAINT ck_lineage_locator CHECK (
    (node_type <> 'raw_locator') OR (locator IS NOT NULL)),
  CONSTRAINT ck_lineage_node_bounded CHECK (
    locator IS NULL OR pg_column_size(locator) <= 4096)
);

-- Una arista. Append-only y con la operacion tipada: `derived_from`,
-- `decided_using` e `included_in_snapshot` no son intercambiables, y mezclarlas
-- convertiria el grafo en un «esto tiene algo que ver con aquello».
CREATE TABLE fincilia.lineage_edge (
  edge_id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  from_node_id             uuid NOT NULL,
  to_node_id               uuid NOT NULL,
  operation                text NOT NULL CHECK (operation IN (
                             'derived_from', 'decided_using', 'included_in_snapshot',
                             'overlay_applied', 'superseded_by', 'redacted_from')),
  transform_ref            text CHECK (transform_ref IS NULL
                             OR length(transform_ref) BETWEEN 1 AND 200),
  actor_kind               text NOT NULL CHECK (actor_kind IN ('human', 'service')),
  actor_id                 uuid NOT NULL,
  workload_identity        text NOT NULL CHECK (length(workload_identity) BETWEEN 1 AND 120),
  processing_run_id        uuid NOT NULL,
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),
  audit_event_ref          uuid,
  occurred_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_lineage_edge_identity UNIQUE (edge_id, company_id),
  CONSTRAINT uq_lineage_edge_natural UNIQUE (from_node_id, to_node_id, operation),
  CONSTRAINT fk_edge_from FOREIGN KEY (from_node_id, company_id)
    REFERENCES fincilia.lineage_node (node_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_edge_to FOREIGN KEY (to_node_id, company_id)
    REFERENCES fincilia.lineage_node (node_id, company_id) ON DELETE RESTRICT,
  CONSTRAINT fk_edge_run FOREIGN KEY (processing_run_id, company_id)
    REFERENCES fincilia.processing_run (run_id, company_id) ON DELETE RESTRICT,
  -- GRAPH-ACYCLIC en su caso mas barato: un nodo no deriva de si mismo.
  CONSTRAINT ck_edge_not_self CHECK (from_node_id <> to_node_id),
  -- `derived_from` significa que el valor fluyo; exige nombrar la transformacion.
  CONSTRAINT ck_edge_transform CHECK (
    operation NOT IN ('derived_from', 'redacted_from') OR transform_ref IS NOT NULL)
);

CREATE INDEX idx_lineage_edge_to ON fincilia.lineage_edge (to_node_id);
CREATE INDEX idx_lineage_edge_from ON fincilia.lineage_edge (from_node_id);

-- --------------------------------------------------------------------------- --
-- Aislamiento
-- --------------------------------------------------------------------------- --

-- FORCE en todas: sin el, el propietario queda exento y el aislamiento es solo
-- aparente. `current_setting(..., true)` devuelve NULL sin contexto, la
-- comparacion es NULL y la politica falla cerrada.
ALTER TABLE fincilia.financial_account ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.financial_account FORCE ROW LEVEL SECURITY;
CREATE POLICY financial_account_isolation ON fincilia.financial_account
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.data_source ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.data_source FORCE ROW LEVEL SECURITY;
CREATE POLICY data_source_isolation ON fincilia.data_source
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.column_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.column_mapping FORCE ROW LEVEL SECURITY;
CREATE POLICY column_mapping_isolation ON fincilia.column_mapping
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.column_mapping_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.column_mapping_version FORCE ROW LEVEL SECURITY;
CREATE POLICY column_mapping_version_isolation ON fincilia.column_mapping_version
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.mapping_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.mapping_decision FORCE ROW LEVEL SECURITY;
CREATE POLICY mapping_decision_isolation ON fincilia.mapping_decision
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.dataset_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.dataset_version FORCE ROW LEVEL SECURITY;
CREATE POLICY dataset_version_isolation ON fincilia.dataset_version
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.reproducibility_manifest ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.reproducibility_manifest FORCE ROW LEVEL SECURITY;
CREATE POLICY reproducibility_manifest_isolation ON fincilia.reproducibility_manifest
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.raw_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.raw_record FORCE ROW LEVEL SECURITY;
CREATE POLICY raw_record_isolation ON fincilia.raw_record
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.source_record ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.source_record FORCE ROW LEVEL SECURITY;
CREATE POLICY source_record_isolation ON fincilia.source_record
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.canonical_movement ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.canonical_movement FORCE ROW LEVEL SECURITY;
CREATE POLICY canonical_movement_isolation ON fincilia.canonical_movement
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.movement_evidence_link ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.movement_evidence_link FORCE ROW LEVEL SECURITY;
CREATE POLICY movement_evidence_link_isolation ON fincilia.movement_evidence_link
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.lineage_node ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.lineage_node FORCE ROW LEVEL SECURITY;
CREATE POLICY lineage_node_isolation ON fincilia.lineage_node
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.lineage_edge ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.lineage_edge FORCE ROW LEVEL SECURITY;
CREATE POLICY lineage_edge_isolation ON fincilia.lineage_edge
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- --------------------------------------------------------------------------- --
-- Privilegios
-- --------------------------------------------------------------------------- --

-- La API prepara, valida y publica; por eso escribe el mapeo y el dataset.
GRANT SELECT ON fincilia.engine_release TO fincilia_app, fincilia_worker;
GRANT SELECT, INSERT, UPDATE ON fincilia.financial_account TO fincilia_app;
GRANT SELECT, INSERT, UPDATE ON fincilia.data_source TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.column_mapping TO fincilia_app;
GRANT SELECT, INSERT, UPDATE ON fincilia.column_mapping_version TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.mapping_decision TO fincilia_app;
GRANT SELECT, INSERT, UPDATE ON fincilia.dataset_version TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.reproducibility_manifest TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.source_record TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.canonical_movement TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.movement_evidence_link TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.lineage_node TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.lineage_edge TO fincilia_app;

-- El worker extrae filas: escribe `raw_record` y nada mas. No publica, no
-- decide ambiguedades y no toca el movimiento canonico. `module-boundaries`
-- lo dice literalmente: los workers no publican estado financiero canonico.
GRANT SELECT, INSERT ON fincilia.raw_record TO fincilia_worker;
GRANT SELECT ON fincilia.raw_record TO fincilia_app;

-- Inmutable para el runtime. Lo publicado no se reescribe: corregir es publicar
-- otra version, y por eso el motor niega el UPDATE en vez de confiar en que
-- nadie lo escriba.
REVOKE UPDATE, DELETE ON fincilia.canonical_movement FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.movement_evidence_link FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.source_record FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.raw_record FROM fincilia_app, fincilia_worker;
REVOKE UPDATE, DELETE ON fincilia.lineage_node FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.lineage_edge FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.mapping_decision FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.reproducibility_manifest FROM fincilia_app;
REVOKE DELETE ON fincilia.dataset_version FROM fincilia_app;
REVOKE DELETE ON fincilia.column_mapping_version FROM fincilia_app;
REVOKE DELETE ON fincilia.column_mapping FROM fincilia_app;
REVOKE DELETE ON fincilia.financial_account FROM fincilia_app;
REVOKE DELETE ON fincilia.data_source FROM fincilia_app;

-- El worker no lee identidad, ni maestros, ni nada publicado.
REVOKE ALL PRIVILEGES ON fincilia.canonical_movement FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.dataset_version FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.financial_account FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.column_mapping_version FROM fincilia_worker;
