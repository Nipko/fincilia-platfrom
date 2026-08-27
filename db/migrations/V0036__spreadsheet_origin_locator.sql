-- FNC-ING-001: el raw_record puede venir de una fila delimitada o de una fila
-- XLSX. La columna del plan sigue siendo 0-based; el localizador spreadsheet
-- conserva fila/hoja 1-based y la celda A1 se reconstruye server-side.

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
      ELSE false
    END);

COMMENT ON CONSTRAINT ck_raw_locator_typed ON fincilia.raw_record IS
  'Solo admite localizadores tabular_delimited o spreadsheet con identidad verificable.';

COMMENT ON CONSTRAINT ck_raw_locator_bounds ON fincilia.raw_record IS
  'La coordenada fisica, el ordinal y la cardinalidad deben coincidir con la fila guardada.';
