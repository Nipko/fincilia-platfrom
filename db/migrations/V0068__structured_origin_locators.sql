-- V0068 (FNC-SMB-002): localizadores de origen para factura DIAN UBL y MT940.
--
-- ADR-039 seccion 5. La promocion ya lee ambos formatos enteros con parsers
-- acotados; aqui `raw_record` aprende a guardar sus coordenadas sin aflojar
-- ninguna de las existentes:
--
--   * `xml_element`: ruta de etiquetas y ordinal del elemento de la factura,
--     mas `field_paths`, una entrada por campo (ruta, lista de rutas si el
--     campo es compuesto, o nulo si el documento no lo trae).
--   * `mt940_tag`: indice de extracto, etiqueta, linea del fichero y lineas del
--     `:86:`, mas `field_tags`, una etiqueta por campo.
--
-- Ambos llevan `parser_release`. El registro de cabecera es sintetico y lo dice
-- (`synthetic_header`): sus columnas las fija el extractor, no el documento.
-- Solo datos sinteticos (DRG-00 sigue vigente).

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

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
      WHEN 'xml_element' THEN
        jsonb_typeof(origin_locator -> 'element_path') = 'string'
        AND jsonb_typeof(origin_locator -> 'element_ordinal') = 'number'
        AND jsonb_typeof(origin_locator -> 'field_paths') = 'array'
        AND jsonb_typeof(origin_locator -> 'parser_release') = 'string'
        AND (NOT (origin_locator ? 'container')
             OR jsonb_typeof(origin_locator -> 'container') = 'string')
      WHEN 'mt940_tag' THEN
        jsonb_typeof(origin_locator -> 'statement_index') = 'number'
        AND jsonb_typeof(origin_locator -> 'tag') = 'string'
        AND jsonb_typeof(origin_locator -> 'line_number') = 'number'
        AND jsonb_typeof(origin_locator -> 'information_lines') = 'array'
        AND jsonb_typeof(origin_locator -> 'field_tags') = 'array'
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
      WHEN 'xml_element' THEN
        (origin_locator ->> 'element_ordinal')::integer BETWEEN 1 AND 100000
        AND (origin_locator ->> 'field_count')::integer <= 64
        AND jsonb_array_length(origin_locator -> 'field_paths') =
            (origin_locator ->> 'field_count')::integer
        AND length(origin_locator ->> 'element_path') BETWEEN 2 AND 1024
        AND (origin_locator ->> 'element_path') LIKE '/%'
        AND pg_column_size(origin_locator) <= 16384
        AND (origin_locator ->> 'parser_release') ~
            '^[a-z0-9][a-z0-9._/+:-]{2,119}$'
      WHEN 'mt940_tag' THEN
        (origin_locator ->> 'statement_index')::integer BETWEEN 1 AND 10000
        AND (origin_locator ->> 'line_number')::integer BETWEEN 1 AND 500000
        AND (origin_locator ->> 'tag') ~ '^[0-9]{2}[A-Z]?$'
        AND (origin_locator ->> 'field_count')::integer <= 64
        AND jsonb_array_length(origin_locator -> 'field_tags') =
            (origin_locator ->> 'field_count')::integer
        AND jsonb_array_length(origin_locator -> 'information_lines') <= 64
        AND (origin_locator ->> 'parser_release') ~
            '^[a-z0-9][a-z0-9._/+:-]{2,119}$'
      ELSE false
    END);

COMMENT ON CONSTRAINT ck_raw_locator_typed ON fincilia.raw_record IS
  'Admite filas delimitadas, hojas, bloques PDF y hechos de factura DIAN o MT940.';
COMMENT ON CONSTRAINT ck_raw_locator_bounds ON fincilia.raw_record IS
  'La coordenada fisica, ordinal y cardinalidad coinciden con la evidencia.';
