-- FNC-CLN-002: una correccion aprobada produce otra version; nunca reescribe
-- el dataset, movimiento, source record ni overlay que la originaron.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- Un apply sincrono tambien es una ejecucion reproducible, pero no entra en la
-- cola del worker: nace y termina en la misma transaccion de la API.
ALTER TABLE fincilia.processing_run DROP CONSTRAINT ck_run_kind;
ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT ck_run_kind
  CHECK (kind IN ('scan', 'profile', 'extract', 'overlay_apply'));

-- Para scan/profile/extract `attempt` sigue siendo el numero de reintento y
-- `max_attempts` lo acota. En las ejecuciones sincronas de overlays identifica
-- versiones sucesivas del mismo artefacto; el techo historico de diez haria que
-- la undécima correccion valida dejara de poder crear historia.
ALTER TABLE fincilia.processing_run
  DROP CONSTRAINT processing_run_attempt_check;
ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT ck_run_attempt_positive CHECK (attempt >= 1);

ALTER TABLE fincilia.dataset_version
  ADD COLUMN supersedes_dataset_version_id uuid;

ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT fk_dataset_supersedes
  FOREIGN KEY (supersedes_dataset_version_id, company_id)
  REFERENCES fincilia.dataset_version (dataset_version_id, company_id)
  ON DELETE RESTRICT;

ALTER TABLE fincilia.dataset_version
  ADD CONSTRAINT ck_dataset_does_not_supersede_itself
  CHECK (supersedes_dataset_version_id IS NULL
         OR supersedes_dataset_version_id <> dataset_version_id);

CREATE TABLE fincilia.field_overlay_application (
  application_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id              uuid NOT NULL REFERENCES fincilia.company(company_id),
  base_dataset_version_id uuid NOT NULL,
  result_dataset_version_id uuid NOT NULL,
  overlay_set_digest      char(64) NOT NULL
                            CHECK (overlay_set_digest ~ '^[0-9a-f]{64}$'),
  applied_by              uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  authorization_version   integer NOT NULL CHECK (authorization_version >= 1),
  applied_at              timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT uq_overlay_application_identity UNIQUE (application_id, company_id),
  CONSTRAINT uq_overlay_application_base UNIQUE (base_dataset_version_id),
  CONSTRAINT uq_overlay_application_result UNIQUE (result_dataset_version_id),
  CONSTRAINT fk_overlay_application_base FOREIGN KEY
    (base_dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_overlay_application_result FOREIGN KEY
    (result_dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_overlay_application_versions_differ CHECK
    (base_dataset_version_id <> result_dataset_version_id)
);

CREATE TABLE fincilia.field_overlay_application_item (
  application_item_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id              uuid NOT NULL REFERENCES fincilia.company(company_id),
  application_id          uuid NOT NULL,
  overlay_id              uuid NOT NULL,
  base_movement_id        uuid NOT NULL,
  result_movement_id      uuid NOT NULL,
  lineage_override_id     uuid NOT NULL,
  original_value_digest   char(64) NOT NULL
                            CHECK (original_value_digest ~ '^[0-9a-f]{64}$'),
  resulting_value_digest  char(64) NOT NULL
                            CHECK (resulting_value_digest ~ '^[0-9a-f]{64}$'),

  CONSTRAINT uq_overlay_application_item_identity
    UNIQUE (application_item_id, company_id),
  CONSTRAINT uq_overlay_applied_once UNIQUE (overlay_id),
  CONSTRAINT uq_overlay_application_target
    UNIQUE (application_id, result_movement_id, overlay_id),
  CONSTRAINT fk_overlay_item_application FOREIGN KEY (application_id, company_id)
    REFERENCES fincilia.field_overlay_application (application_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_overlay_item_overlay FOREIGN KEY (overlay_id, company_id)
    REFERENCES fincilia.field_overlay (overlay_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_overlay_item_base_movement FOREIGN KEY (base_movement_id, company_id)
    REFERENCES fincilia.canonical_movement (movement_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_overlay_item_result_movement FOREIGN KEY (result_movement_id, company_id)
    REFERENCES fincilia.canonical_movement (movement_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_overlay_item_lineage_override FOREIGN KEY
    (lineage_override_id, company_id)
    REFERENCES fincilia.lineage_row_override (override_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_overlay_application_changes_value
    CHECK (original_value_digest <> resulting_value_digest)
);

CREATE INDEX idx_overlay_application_company_time
  ON fincilia.field_overlay_application (company_id, applied_at DESC);
CREATE INDEX idx_overlay_application_items
  ON fincilia.field_overlay_application_item (application_id, overlay_id);

ALTER TABLE fincilia.field_overlay_application ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.field_overlay_application FORCE ROW LEVEL SECURITY;
CREATE POLICY field_overlay_application_isolation
  ON fincilia.field_overlay_application
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.field_overlay_application_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.field_overlay_application_item FORCE ROW LEVEL SECURITY;
CREATE POLICY field_overlay_application_item_isolation
  ON fincilia.field_overlay_application_item
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

GRANT SELECT, INSERT ON fincilia.field_overlay_application TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.field_overlay_application_item TO fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.field_overlay_application FROM fincilia_app;
REVOKE UPDATE, DELETE ON fincilia.field_overlay_application_item FROM fincilia_app;
REVOKE ALL PRIVILEGES ON fincilia.field_overlay_application FROM fincilia_worker;
REVOKE ALL PRIVILEGES ON fincilia.field_overlay_application_item FROM fincilia_worker;
