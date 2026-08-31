-- FNC-ING-006: localizador verificable de un bloque de texto PDF.
-- No cambia la semántica financiera: solo amplía la procedencia física que un
-- raw_record puede declarar. PDF nunca publica directamente.

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
      ELSE false
    END);

COMMENT ON CONSTRAINT ck_raw_locator_typed ON fincilia.raw_record IS
  'Admite filas delimitadas, hojas de cálculo o bloques PDF pasivos con identidad verificable.';

COMMENT ON CONSTRAINT ck_raw_locator_bounds ON fincilia.raw_record IS
  'La coordenada física, ordinal y cardinalidad coinciden con la evidencia guardada.';
