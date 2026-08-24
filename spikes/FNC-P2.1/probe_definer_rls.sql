-- Sonda de semantica de PostgreSQL para el diseno de FNC-P2.1.
--
-- Cinco preguntas de las que depende el diseno, y ninguna se contesta con
-- seguridad suficiente leyendo documentacion: se contestan contra el motor.
--
-- 1. Una funcion SECURITY DEFINER cuyo propietario es tambien el propietario de
--    la tabla, ¿se salta FORCE ROW LEVEL SECURITY?
-- 2. ¿Puede un rol no superusuario declarar una clausula `SET` de un GUC
--    personalizado a nivel de funcion, para que se restaure al salir?
-- 3. Si no, ¿basta con guardar y restaurar el contexto a mano dentro de la
--    funcion?
-- 4. ¿Funciona FOR UPDATE SKIP LOCKED dentro de un CTE que luego actualiza?
-- 5. ¿Puede un rol sin UPDATE escribir a traves de una funcion SECURITY DEFINER?
--
-- Se ejecuta contra el esquema desechable `probe`. No toca `fincilia`.

\set ON_ERROR_STOP on

DROP SCHEMA IF EXISTS probe CASCADE;
CREATE SCHEMA probe;

CREATE TABLE probe.scoped (
  id         int PRIMARY KEY,
  company_id text NOT NULL,
  payload    text NOT NULL
);

ALTER TABLE probe.scoped ENABLE ROW LEVEL SECURITY;
ALTER TABLE probe.scoped FORCE ROW LEVEL SECURITY;
CREATE POLICY scoped_isolation ON probe.scoped
  USING (company_id = current_setting('probe.company_id', true))
  WITH CHECK (company_id = current_setting('probe.company_id', true));

SELECT set_config('probe.company_id', 'A', false);
INSERT INTO probe.scoped VALUES (1, 'A', 'de A');
SELECT set_config('probe.company_id', 'B', false);
INSERT INTO probe.scoped VALUES (2, 'B', 'de B');
SELECT set_config('probe.company_id', '', false);

-- --------------------------------------------------------------------------- --
-- 1. SECURITY DEFINER contra FORCE RLS
-- --------------------------------------------------------------------------- --

CREATE FUNCTION probe.count_without_context() RETURNS bigint
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, probe AS $$
  SELECT count(*) FROM probe.scoped;
$$;

\echo '== 1. SECURITY DEFINER sin contexto (0 significa que FORCE alcanza al definer) =='
SELECT probe.count_without_context() AS filas_visibles;

-- --------------------------------------------------------------------------- --
-- 3. Guardar y restaurar el contexto a mano
--    (la pregunta 2 ya se contesto: un rol no superusuario no puede declarar
--    `SET "probe.company_id"` a nivel de funcion; da «permission denied to set
--    parameter». Por eso hay que restaurar a mano.)
-- --------------------------------------------------------------------------- --

CREATE FUNCTION probe.read_scoped(p_company text)
RETURNS TABLE (id int, payload text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, probe
AS $$
DECLARE
  v_previous text := current_setting('probe.company_id', true);
BEGIN
  PERFORM set_config('probe.company_id', p_company, true);
  RETURN QUERY SELECT s.id, s.payload FROM probe.scoped s;
  PERFORM set_config('probe.company_id', coalesce(v_previous, ''), true);
END;
$$;

\echo '== 3a. La funcion fija el contexto y ve solo su empresa =='
SELECT * FROM probe.read_scoped('A');

\echo '== 3b. Al salir, el contexto del llamante quedo restaurado (esperado vacio) =='
SELECT coalesce(current_setting('probe.company_id', true), '(nulo)') AS contexto_tras_llamada;
SELECT count(*) AS filas_visibles_para_el_llamante FROM probe.scoped;

-- --------------------------------------------------------------------------- --
-- 4. FOR UPDATE SKIP LOCKED dentro de un CTE que actualiza
-- --------------------------------------------------------------------------- --

CREATE TABLE probe.queue (
  run_id       int PRIMARY KEY,
  available_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO probe.queue (run_id) VALUES (1), (2), (3);

\echo '== 4. CTE con FOR UPDATE SKIP LOCKED y UPDATE =='
WITH candidato AS (
  SELECT q.run_id
  FROM probe.queue q
  WHERE q.available_at <= now()
  ORDER BY q.available_at
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE probe.queue AS t
SET available_at = now() + interval '5 minutes'
FROM candidato
WHERE t.run_id = candidato.run_id
RETURNING t.run_id;

-- --------------------------------------------------------------------------- --
-- 5. Un rol sin privilegio escribiendo a traves de SECURITY DEFINER
-- --------------------------------------------------------------------------- --

CREATE FUNCTION probe.touch(p_run_id int) RETURNS int
LANGUAGE sql SECURITY DEFINER SET search_path = pg_catalog, probe AS $$
  UPDATE probe.queue SET available_at = now() WHERE run_id = p_run_id
  RETURNING run_id;
$$;

REVOKE ALL ON FUNCTION probe.touch(int) FROM PUBLIC;
GRANT USAGE ON SCHEMA probe TO fincilia_app;
GRANT EXECUTE ON FUNCTION probe.touch(int) TO fincilia_app;

\echo '== 5. Estructura lista. `fincilia_app` NO tiene UPDATE sobre probe.queue =='
SELECT has_table_privilege('fincilia_app', 'probe.queue', 'UPDATE') AS app_tiene_update,
       has_function_privilege('fincilia_app', 'probe.touch(int)', 'EXECUTE') AS app_puede_ejecutar;

-- --------------------------------------------------------------------------- --
-- 6. ¿Una FK compuesta puede apuntar a (PK, otra columna)?
-- --------------------------------------------------------------------------- --

CREATE TABLE probe.parent (
  run_id     int PRIMARY KEY,
  company_id text NOT NULL
);
CREATE TABLE probe.child (
  run_id     int PRIMARY KEY,
  company_id text NOT NULL
);

\echo '== 6a. FK compuesta sin UNIQUE en el destino (debe fallar) =='
DO $$
BEGIN
  BEGIN
    ALTER TABLE probe.child ADD CONSTRAINT fk_sin_unique
      FOREIGN KEY (run_id, company_id) REFERENCES probe.parent (run_id, company_id);
    RAISE NOTICE 'INESPERADO: la FK compuesta se acepto sin UNIQUE';
  EXCEPTION WHEN others THEN
    RAISE NOTICE 'esperado: %', SQLERRM;
  END;
END
$$;

ALTER TABLE probe.parent ADD CONSTRAINT uq_parent_run_company UNIQUE (run_id, company_id);
ALTER TABLE probe.child ADD CONSTRAINT fk_con_unique
  FOREIGN KEY (run_id, company_id) REFERENCES probe.parent (run_id, company_id);

INSERT INTO probe.parent VALUES (1, 'A');

\echo '== 6b. Puntero cruzado (run de A con company B) debe ser rechazado =='
DO $$
BEGIN
  BEGIN
    INSERT INTO probe.child VALUES (1, 'B');
    RAISE NOTICE 'INESPERADO: se acepto un puntero cruzado';
  EXCEPTION WHEN foreign_key_violation THEN
    RAISE NOTICE 'esperado: rechazado por clave ajena';
  END;
END
$$;

INSERT INTO probe.child VALUES (1, 'A');
\echo '== 6c. Puntero coherente aceptado =='
SELECT count(*) AS punteros FROM probe.child;
