-- --------------------------------------------------------------------------- --
-- V0012 — La via de excepcion por fila (FNC-P3.6, ADR-024)
--
-- El plan de V0009 explica **la columna**, y eso basta para noventa y nueve mil
-- filas de cada cien mil: leer la columna 3 como decimal con coma es la misma
-- decision en la fila 7 que en la 90.000.
--
-- Lo que ADR-024 dejaba sin contestar es la fila que se aparta de esa regla:
-- alguien corrigio el importe a mano, alguien resolvio el signo mirando el
-- documento, una fila se rechazo. Sin sitio donde decirlo, esa correccion o
-- desaparece del camino —y el linaje afirma algo falso— o obliga a romper el
-- plan compartido para acomodar una excepcion, que es la premisa entera del
-- ADR.
--
-- Aqui se guarda **donde** ocurrio, **de que clase** fue, **por que**, y las
-- huellas de antes y de despues. El valor no: con las dos huellas se comprueba
-- que el override describe este caso y no otro, y sin el valor se puede seguir
-- diciendo que el grafo de linaje no almacena importes.
-- --------------------------------------------------------------------------- --

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- --------------------------------------------------------------------------- --
-- 1. La tabla
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.lineage_row_override (
  override_id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  dataset_version_id       uuid NOT NULL,
  source_record_id         uuid NOT NULL,
  raw_record_id            uuid NOT NULL,
  field_name               text NOT NULL CHECK (length(field_name) BETWEEN 1 AND 64),
  -- A que etapa del plan se engancha. Es un paso concreto, no un numero suelto:
  -- de ahi sale la posicion logica en la que el drill-down lo intercala.
  base_plan_step_id        uuid NOT NULL,
  override_kind            text NOT NULL CHECK (override_kind IN (
                             'manual_correction', 'overlay_applied',
                             'exceptional_parse', 'sign_resolution',
                             'substituted_value', 'rejected_value', 'row_rule')),
  -- Lo que el plan habria producido, y lo que se publico. Huellas, nunca valores.
  original_value_digest    char(64) NOT NULL CHECK (original_value_digest ~ '^[0-9a-f]{64}$'),
  resulting_value_digest   char(64) NOT NULL CHECK (resulting_value_digest ~ '^[0-9a-f]{64}$'),
  rule_version             text NOT NULL CHECK (length(rule_version) BETWEEN 1 AND 64),
  reason_code              text NOT NULL CHECK (length(reason_code) BETWEEN 1 AND 64),
  -- Un override sustituye al anterior sobre el mismo campo de la misma fila. El
  -- anterior no se borra ni se edita: se queda, y el vigente es el de ordinal
  -- mas alto. Cambiar de opinion deja rastro de las dos opiniones.
  override_ordinal         integer NOT NULL DEFAULT 1 CHECK (override_ordinal >= 1),
  created_by               uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  approved_by              uuid REFERENCES fincilia.subject(subject_id),
  approved_at              timestamptz,
  created_at               timestamptz NOT NULL DEFAULT now(),
  engine_release_id        uuid NOT NULL REFERENCES fincilia.engine_release(release_id),
  canonical_schema_version text NOT NULL CHECK (length(canonical_schema_version) BETWEEN 1 AND 32),

  CONSTRAINT uq_override_identity UNIQUE (override_id, company_id),
  -- Un vigente por campo y fila dentro de una version del dataset.
  CONSTRAINT uq_override_target UNIQUE (dataset_version_id, source_record_id,
                                        field_name, override_ordinal),
  CONSTRAINT fk_override_dataset FOREIGN KEY (dataset_version_id, company_id)
    REFERENCES fincilia.dataset_version (dataset_version_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_override_source_record FOREIGN KEY (source_record_id, company_id)
    REFERENCES fincilia.source_record (source_record_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_override_raw_record FOREIGN KEY (raw_record_id, company_id)
    REFERENCES fincilia.raw_record (raw_record_id, company_id)
    ON DELETE RESTRICT,
  CONSTRAINT fk_override_plan_step FOREIGN KEY (base_plan_step_id, company_id)
    REFERENCES fincilia.lineage_transform_step (step_id, company_id)
    ON DELETE RESTRICT,
  -- Quien lo escribe no lo aprueba. Esta en la base y no solo en la API: la de
  -- la API da un mensaje util, y esta aguanta cuando alguien llega por otro
  -- camino.
  CONSTRAINT ck_override_segregation CHECK (approved_by IS NULL
                                            OR approved_by <> created_by),
  CONSTRAINT ck_override_approval_pair CHECK ((approved_by IS NULL) = (approved_at IS NULL)),
  -- Un override que no cambia nada no es un override: si las dos huellas
  -- coinciden, lo que se publico es lo que el plan producia.
  CONSTRAINT ck_override_changes_something CHECK (original_value_digest
                                                  <> resulting_value_digest)
);

CREATE INDEX idx_override_dataset
  ON fincilia.lineage_row_override (dataset_version_id, source_record_id, field_name);

-- Los que aun no ha mirado nadie. Es la consulta que bloquea la publicacion, y
-- se hace una vez por dataset: merece su indice.
CREATE INDEX idx_override_unapproved
  ON fincilia.lineage_row_override (dataset_version_id)
  WHERE approved_by IS NULL;

COMMENT ON TABLE fincilia.lineage_row_override IS
  'Excepcion por fila al plan de transformacion de su columna (ADR-024). '
  'Guarda huellas y motivos, jamas valores.';

-- --------------------------------------------------------------------------- --
-- 2. Inmutable, salvo el sello de aprobacion
-- --------------------------------------------------------------------------- --

-- Un override no se edita: describe algo que ya paso. Lo unico que puede pasarle
-- despues es que alguien distinto lo apruebe, una vez y en un solo sentido.
--
-- El borrado no lo cubre este disparador sino el privilegio que no se concede:
-- `fincilia_app` recibe `SELECT, INSERT, UPDATE` y nada mas, igual que el plan
-- de linaje. Un `RAISE` en el `DELETE` no anadiria una garantia —el runtime ya
-- no puede— y a cambio dejaria una tabla que el dueno del esquema no puede
-- limpiar ni al retirar una empresa.
CREATE FUNCTION fincilia.lineage_row_override_is_append_only()
RETURNS trigger
LANGUAGE plpgsql
AS $append_only$
BEGIN
  IF OLD.approved_by IS NOT NULL THEN
    RAISE EXCEPTION 'an approved lineage row override is immutable'
      USING ERRCODE = '23514';
  END IF;

  IF (NEW.override_id, NEW.company_id, NEW.dataset_version_id, NEW.source_record_id,
      NEW.raw_record_id, NEW.field_name, NEW.base_plan_step_id, NEW.override_kind,
      NEW.original_value_digest, NEW.resulting_value_digest, NEW.rule_version,
      NEW.reason_code, NEW.override_ordinal, NEW.created_by, NEW.created_at,
      NEW.engine_release_id, NEW.canonical_schema_version)
     IS DISTINCT FROM
     (OLD.override_id, OLD.company_id, OLD.dataset_version_id, OLD.source_record_id,
      OLD.raw_record_id, OLD.field_name, OLD.base_plan_step_id, OLD.override_kind,
      OLD.original_value_digest, OLD.resulting_value_digest, OLD.rule_version,
      OLD.reason_code, OLD.override_ordinal, OLD.created_by, OLD.created_at,
      OLD.engine_release_id, OLD.canonical_schema_version) THEN
    RAISE EXCEPTION 'a lineage row override only changes to record its approval'
      USING ERRCODE = '23514';
  END IF;

  IF NEW.approved_by IS NULL THEN
    RAISE EXCEPTION 'approving a lineage row override needs an approver'
      USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$append_only$;

REVOKE ALL PRIVILEGES ON FUNCTION fincilia.lineage_row_override_is_append_only()
  FROM PUBLIC;

CREATE TRIGGER lineage_row_override_append_only
  BEFORE UPDATE ON fincilia.lineage_row_override
  FOR EACH ROW EXECUTE FUNCTION fincilia.lineage_row_override_is_append_only();

-- --------------------------------------------------------------------------- --
-- 3. Aislamiento
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.lineage_row_override ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.lineage_row_override FORCE ROW LEVEL SECURITY;
CREATE POLICY lineage_row_override_isolation ON fincilia.lineage_row_override
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- --------------------------------------------------------------------------- --
-- 4. Privilegios
-- --------------------------------------------------------------------------- --

-- `UPDATE` esta ahi por el sello de aprobacion y por nada mas: el disparador de
-- arriba es quien decide que se puede cambiar. **Sin `DELETE`**: el runtime no
-- borra una excepcion, del mismo modo que no borra un paso del plan.
GRANT SELECT, INSERT, UPDATE ON fincilia.lineage_row_override TO fincilia_app;
