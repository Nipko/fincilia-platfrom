-- --------------------------------------------------------------------------- --
-- V0014 — Indices de soporte para evidencia cruda (FNC-P3.6-R2)
--
-- El carril de 200.000 filas encontro una degradacion que una prueba pequena no
-- podia mostrar: retirar 600.000 `raw_record` tardaba mas de quince minutos.
-- `source_record` y `lineage_row_override` referencian la clave compuesta del
-- registro crudo, pero ninguno tenia un indice que comenzara por esa FK. Para
-- comprobar un DELETE de la fila padre PostgreSQL debia buscar hijos una vez por
-- cada fila. El indice del artefacto tambien evita barrer toda la tabla al
-- aplicar retencion a una version concreta del archivo.
--
-- No cambia semantica financiera, RLS ni privilegios. Solo materializa los
-- caminos de acceso que ya exige el esquema relacional.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE INDEX idx_raw_record_artifact_company
  ON fincilia.raw_record (artifact_id, company_id);

CREATE INDEX idx_source_record_raw_company
  ON fincilia.source_record (raw_record_id, company_id);

CREATE INDEX idx_lineage_row_override_raw_company
  ON fincilia.lineage_row_override (raw_record_id, company_id);

COMMENT ON INDEX fincilia.idx_raw_record_artifact_company IS
  'Soporta seleccion y retencion de evidencia por version exacta del artefacto.';

COMMENT ON INDEX fincilia.idx_source_record_raw_company IS
  'Soporta la FK hacia raw_record y evita comprobaciones cuadraticas al retirar evidencia.';

COMMENT ON INDEX fincilia.idx_lineage_row_override_raw_company IS
  'Soporta la FK de overrides por fila hacia la evidencia cruda.';
