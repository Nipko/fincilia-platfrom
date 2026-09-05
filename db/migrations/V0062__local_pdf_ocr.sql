-- FNC-ING-007: derivado OCR local, company-scoped e inmutable.
-- El texto reconocido vive exclusivamente en object storage derivado. Esta
-- tabla conserva identidad, versión, tamaño y vínculo exacto con el original.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.source_artifact
  ADD CONSTRAINT uq_source_artifact_company_identity
  UNIQUE (company_id, artifact_id, content_sha256);

ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT uq_processing_run_company_identity
  UNIQUE (company_id, artifact_id, run_id, kind);

CREATE TABLE fincilia.pdf_ocr_result (
  ocr_result_id uuid PRIMARY KEY,
  company_id uuid NOT NULL REFERENCES fincilia.company(company_id)
    ON DELETE RESTRICT,
  artifact_id uuid NOT NULL,
  scan_run_id uuid NOT NULL,
  scan_kind text NOT NULL DEFAULT 'scan' CHECK (scan_kind = 'scan'),
  source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
  derived_object_key text NOT NULL CHECK (length(derived_object_key) BETWEEN 80 AND 640),
  derived_sha256 text NOT NULL CHECK (derived_sha256 ~ '^[0-9a-f]{64}$'),
  ocr_release text NOT NULL CHECK (
    ocr_release ~ '^[a-z0-9][a-z0-9._/+:-]{2,119}$'),
  language_set text[] NOT NULL CHECK (
    cardinality(language_set) BETWEEN 1 AND 4
    AND array_position(language_set, NULL) IS NULL
    AND array_to_string(language_set, ',') ~ '^[a-z]{3}(,[a-z]{3}){0,3}$'),
  page_count integer NOT NULL CHECK (page_count BETWEEN 1 AND 50),
  block_count integer NOT NULL CHECK (block_count BETWEEN 1 AND 200000),
  requires_human_review boolean NOT NULL DEFAULT true
    CHECK (requires_human_review IS true),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  CONSTRAINT fk_pdf_ocr_source_exact FOREIGN KEY (
    company_id, artifact_id, source_sha256
  ) REFERENCES fincilia.source_artifact (
    company_id, artifact_id, content_sha256
  ) ON DELETE RESTRICT,
  CONSTRAINT fk_pdf_ocr_scan_company FOREIGN KEY (
    company_id, artifact_id, scan_run_id, scan_kind
  ) REFERENCES fincilia.processing_run (
    company_id, artifact_id, run_id, kind
  ) ON DELETE RESTRICT,
  CONSTRAINT uq_pdf_ocr_artifact_release UNIQUE (artifact_id, ocr_release),
  CONSTRAINT uq_pdf_ocr_derived_digest UNIQUE (company_id, derived_sha256),
  CONSTRAINT ck_pdf_ocr_object_key CHECK (
    derived_object_key = 'company/' || company_id::text || '/' ||
      left(derived_sha256, 2) || '/' || derived_sha256 || '.ocr.json')
);

REVOKE ALL PRIVILEGES ON fincilia.pdf_ocr_result FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.pdf_ocr_result
  FROM fincilia_app, fincilia_worker;
GRANT SELECT, INSERT ON fincilia.pdf_ocr_result TO fincilia_worker;

ALTER TABLE fincilia.pdf_ocr_result ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.pdf_ocr_result FORCE ROW LEVEL SECURITY;
CREATE POLICY pdf_ocr_result_worker_isolation ON fincilia.pdf_ocr_result
  TO fincilia_worker
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.raw_record
  DROP CONSTRAINT ck_raw_locator_typed,
  DROP CONSTRAINT ck_raw_locator_bounds;

ALTER TABLE fincilia.raw_record
  ADD CONSTRAINT ck_raw_locator_typed CHECK (
    jsonb_typeof(origin_locator) = 'object'
    AND jsonb_typeof(origin_locator -> 'locator_kind') = 'string'
    AND jsonb_typeof(origin_locator -> 'artifact_sha256') = 'string'
    AND (origin_locator ->> 'artifact_sha256') ~ '^[0-9a-f]{64}$'
    AND jsonb_typeof(origin_locator -> 'record_ordinal') = 'number'
    AND jsonb_typeof(origin_locator -> 'field_count') = 'number'
    AND CASE origin_locator ->> 'locator_kind'
      WHEN 'tabular_delimited' THEN
        jsonb_typeof(origin_locator -> 'byte_start') = 'number'
        AND jsonb_typeof(origin_locator -> 'byte_end') = 'number'
      WHEN 'spreadsheet' THEN
        jsonb_typeof(origin_locator -> 'row_number') = 'number'
        AND jsonb_typeof(origin_locator -> 'sheet_ordinal') = 'number'
        AND jsonb_typeof(origin_locator -> 'workbook_identity') = 'string'
        AND jsonb_typeof(origin_locator -> 'sheet_identity') = 'string'
        AND (origin_locator ->> 'workbook_identity') ~ '^[0-9a-f]{64}$'
        AND (origin_locator ->> 'sheet_identity') ~ '^[0-9a-f]{64}$'
      WHEN 'pdf_text' THEN
        jsonb_typeof(origin_locator -> 'page_number') = 'number'
        AND jsonb_typeof(origin_locator -> 'block_ordinal') = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox') = 'array'
        AND jsonb_array_length(origin_locator -> 'bbox') = 4
        AND jsonb_typeof(origin_locator -> 'confidence') = 'number'
        AND jsonb_typeof(origin_locator -> 'parser_release') = 'string'
      WHEN 'pdf_ocr' THEN
        jsonb_typeof(origin_locator -> 'page_number') = 'number'
        AND jsonb_typeof(origin_locator -> 'block_ordinal') = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox') = 'array'
        AND jsonb_array_length(origin_locator -> 'bbox') = 4
        AND jsonb_typeof(origin_locator -> 'confidence') = 'number'
        AND jsonb_typeof(origin_locator -> 'ocr_release') = 'string'
      ELSE false
    END),
  ADD CONSTRAINT ck_raw_locator_bounds CHECK (
    (origin_locator ->> 'record_ordinal')::integer = record_ordinal
    AND (origin_locator ->> 'field_count')::integer >= 1
    AND jsonb_array_length(raw_values) =
        (origin_locator ->> 'field_count')::integer
    AND CASE origin_locator ->> 'locator_kind'
      WHEN 'tabular_delimited' THEN
        (origin_locator ->> 'byte_start')::bigint >= 0
        AND (origin_locator ->> 'byte_end')::bigint >
            (origin_locator ->> 'byte_start')::bigint
      WHEN 'spreadsheet' THEN
        (origin_locator ->> 'row_number')::integer = record_ordinal
        AND (origin_locator ->> 'row_number')::integer BETWEEN 1 AND 1048576
        AND (origin_locator ->> 'sheet_ordinal')::integer >= 1
        AND (origin_locator ->> 'field_count')::integer <= 512
      WHEN 'pdf_text' THEN
        (origin_locator ->> 'page_number')::integer BETWEEN 1 AND 250
        AND (origin_locator ->> 'block_ordinal')::integer BETWEEN 1 AND 200000
        AND (origin_locator ->> 'field_count')::integer <= 512
        AND (origin_locator ->> 'confidence')::numeric BETWEEN 0 AND 1
        AND jsonb_typeof(origin_locator -> 'bbox' -> 0) = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox' -> 1) = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox' -> 2) = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox' -> 3) = 'number'
        AND (origin_locator -> 'bbox' ->> 0)::numeric BETWEEN 0 AND 1
        AND (origin_locator -> 'bbox' ->> 1)::numeric BETWEEN 0 AND 1
        AND (origin_locator -> 'bbox' ->> 2)::numeric BETWEEN 0 AND 1
        AND (origin_locator -> 'bbox' ->> 3)::numeric BETWEEN 0 AND 1
      WHEN 'pdf_ocr' THEN
        (origin_locator ->> 'page_number')::integer BETWEEN 1 AND 50
        AND (origin_locator ->> 'block_ordinal')::integer BETWEEN 1 AND 200000
        AND (origin_locator ->> 'field_count')::integer = 1
        AND (origin_locator ->> 'confidence')::numeric BETWEEN 0 AND 1
        AND jsonb_typeof(origin_locator -> 'bbox' -> 0) = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox' -> 1) = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox' -> 2) = 'number'
        AND jsonb_typeof(origin_locator -> 'bbox' -> 3) = 'number'
        AND (origin_locator -> 'bbox' ->> 0)::numeric BETWEEN 0 AND 1
        AND (origin_locator -> 'bbox' ->> 1)::numeric BETWEEN 0 AND 1
        AND (origin_locator -> 'bbox' ->> 2)::numeric BETWEEN 0 AND 1
        AND (origin_locator -> 'bbox' ->> 3)::numeric BETWEEN 0 AND 1
        AND (origin_locator ->> 'bbox') IS NOT NULL
        AND (origin_locator ->> 'ocr_release') ~
            '^[a-z0-9][a-z0-9._/+:-]{2,119}$'
      ELSE false
    END);

COMMENT ON TABLE fincilia.pdf_ocr_result IS
  'Metadata inmutable del OCR local; el texto vive en el objeto derivado.';
COMMENT ON CONSTRAINT ck_raw_locator_typed ON fincilia.raw_record IS
  'Admite filas delimitadas, hojas y bloques PDF embebidos u OCR verificables.';
COMMENT ON CONSTRAINT ck_raw_locator_bounds ON fincilia.raw_record IS
  'La coordenada física, ordinal y cardinalidad coinciden con la evidencia.';
