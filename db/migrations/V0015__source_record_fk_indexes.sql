-- --------------------------------------------------------------------------- --
-- V0015 — Indices de soporte para el registro tipado (FNC-P3.6-R2)
--
-- V0014 resolvio el primer nivel del grafo de evidencia. Al repetir el carril,
-- la siguiente retencion explicita mostro el mismo defecto un nivel mas arriba:
-- tres tablas referencian `source_record_id`, pero sus indices existentes
-- empiezan por dataset o movimiento. Despues de retirar los hijos, PostgreSQL
-- aun debe demostrar para cada padre que no queda ninguna referencia; sin estos
-- indices esa demostracion vuelve a barrer tablas grandes.
--
-- Es una migracion hacia adelante porque V0014 ya fue aplicada y verificada. No
-- cambia RLS, ACL, estados ni semantica financiera.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE INDEX idx_canonical_movement_source_company
  ON fincilia.canonical_movement (source_record_id, company_id);

CREATE INDEX idx_movement_evidence_source_company
  ON fincilia.movement_evidence_link (source_record_id, company_id);

CREATE INDEX idx_lineage_row_override_source_company
  ON fincilia.lineage_row_override (source_record_id, company_id);

COMMENT ON INDEX fincilia.idx_canonical_movement_source_company IS
  'Soporta la FK hacia source_record durante retencion y comprobaciones de integridad.';

COMMENT ON INDEX fincilia.idx_movement_evidence_source_company IS
  'Soporta la FK de evidencia hacia source_record sin barridos por cada padre.';

COMMENT ON INDEX fincilia.idx_lineage_row_override_source_company IS
  'Soporta la FK de overrides hacia el registro tipado.';
