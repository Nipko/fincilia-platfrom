-- Driver de aplicacion de UNA migracion (FNC-DB-002).
--
-- Se invoca con psql --single-transaction, de modo que la operacion de abajo vive en
-- una sola transaccion: si algo falla, no queda ni objeto a medias ni fila de
-- historial. Variables esperadas: version, name, checksum, file.
--
-- Orden deliberado:
--   1. lock: serializa migradores concurrentes; se libera al terminar la transaccion
--   2. checksum: si la version ya esta aplicada con OTRO contenido, aborta ANTES de ejecutar
--   3. guard: si ya esta aplicada con el MISMO contenido, no se repite
--   4. aplicar e insertar historial
--
-- Nota sobre psql: la sustitucion de `:'variable'` NO ocurre dentro de un bloque
-- entrecomillado con dolares. Por eso los valores entran primero como ajustes de
-- sesion con SET LOCAL, que si admite interpolacion, y el bloque DO los lee con
-- current_setting. Interpolar dentro del bloque daria un error de sintaxis.

\set ON_ERROR_STOP on

SELECT pg_advisory_xact_lock(hashtext('fincilia_db_spike_migration'));

SET LOCAL fincilia.migration_version = :'version';
SET LOCAL fincilia.migration_checksum = :'checksum';

DO $checksum_guard$
DECLARE
  wanted_version  text := current_setting('fincilia.migration_version', true);
  wanted_checksum text := current_setting('fincilia.migration_checksum', true);
  recorded        text;
BEGIN
  IF wanted_version IS NULL OR wanted_checksum IS NULL THEN
    RAISE EXCEPTION 'FNC_SPIKE_MISSING_CONTEXT version or checksum was not provided';
  END IF;

  SELECT checksum INTO recorded
  FROM spike.schema_history
  WHERE version = wanted_version;

  IF recorded IS NOT NULL AND recorded IS DISTINCT FROM wanted_checksum THEN
    RAISE EXCEPTION
      'FNC_SPIKE_CHECKSUM_MISMATCH version=% recorded=% incoming=%',
      wanted_version, recorded, wanted_checksum;
  END IF;
END
$checksum_guard$;

SELECT NOT EXISTS (
  SELECT 1 FROM spike.schema_history WHERE version = :'version'
) AS fnc_should_apply \gset

\if :fnc_should_apply
  \echo 'FNC_SPIKE_APPLYING' :version
  \i :file
  INSERT INTO spike.schema_history (version, name, checksum, status)
  VALUES (:'version', :'name', :'checksum', 'applied');
  \echo 'FNC_SPIKE_APPLIED' :version
\else
  \echo 'FNC_SPIKE_ALREADY_APPLIED' :version
\endif
