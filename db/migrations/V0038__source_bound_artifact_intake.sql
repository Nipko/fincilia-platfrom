-- FNC-ING-003: una recepcion pertenece a la fuente declarada al cargarla.
--
-- V0009 agrego `data_source_id` nullable para no inventar procedencia sobre
-- evidencia historica. Desde esta version la API siempre lo escribe. La
-- unicidad anterior por empresa mezclaba dos recepciones legitimas cuando dos
-- fuentes entregaban exactamente los mismos bytes.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.source_artifact
  DROP CONSTRAINT uq_artifact_content;

CREATE UNIQUE INDEX uq_artifact_source_content
  ON fincilia.source_artifact(company_id, data_source_id, content_sha256)
  WHERE data_source_id IS NOT NULL;

-- Lo legacy sigue siendo idempotente dentro de su empresa, pero nunca se le
-- atribuye una fuente por similitud, nombre ni mapeo posterior.
CREATE UNIQUE INDEX uq_artifact_legacy_content
  ON fincilia.source_artifact(company_id, content_sha256)
  WHERE data_source_id IS NULL;

COMMENT ON COLUMN fincilia.source_artifact.data_source_id IS
  'Fuente inmutable declarada al recibir; NULL solo para evidencia legacy no atribuible.';
