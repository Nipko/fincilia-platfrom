-- V0007: cuarentena antes que evidencia, con la decision escrita.
--
-- `docs/architecture/dfd-flows.json` declara dos flujos distintos y este esquema
-- los tenia colapsados en uno:
--
--   F02 `upload_to_quarantine`   -> authoritative_effect: evidence_quarantine_only
--   F03 `scan_and_promote_to_raw` -> controls: C-SCAN (content_scan_before_raw)
--                                    persistence: postgresql, scan_and_promotion_decision
--
-- Hasta ahora la subida decidia la zona en la misma peticion, y solo miraba
-- dentro de los ficheros de texto. Un PDF, un ZIP o una hoja de calculo entraban
-- directamente a `raw` **sin que nadie hubiera leido su contenido**, que es justo
-- lo que C-SCAN prohibe.
--
-- La correccion no es escanear mas formatos: es dejar de promover lo que no se
-- sabe leer. Un PDF se queda en cuarentena con el motivo escrito, y ahi seguira
-- hasta que exista un analizador seguro. Prometer que esta soportado seria peor
-- que decir que no lo esta.
--
-- Esto **no resuelve** S-01 ni TM-005. La deteccion de PAN antes de `raw` sigue
-- dependiendo de una decision humana de Security que sigue pendiente, y el
-- fichero con PAN sigue aterrizando en cuarentena antes de detectarlo, que es la
-- cuestion de alcance PCI todavia abierta. Lo que cambia es que ahora nada sale
-- de cuarentena sin inspeccion, que es estrictamente mas conservador.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- --------------------------------------------------------------------------- --
-- 1. El escaneo es un trabajo mas de la cola
-- --------------------------------------------------------------------------- --

-- La misma lista vive en tres sitios: la restriccion del trabajo, la del puntero
-- y la validacion de la funcion de encolado. Ampliar uno solo produce un fallo
-- que no menciona a los otros dos, asi que se amplian los tres juntos y una
-- prueba comprueba contra la base que siguen coincidiendo.
ALTER TABLE fincilia.processing_run DROP CONSTRAINT processing_run_kind_check;
ALTER TABLE fincilia.processing_run
  ADD CONSTRAINT ck_run_kind CHECK (kind IN ('scan', 'profile', 'extract'));

ALTER TABLE fincilia.dispatch_pointer DROP CONSTRAINT dispatch_pointer_kind_check;
ALTER TABLE fincilia.dispatch_pointer
  ADD CONSTRAINT ck_dispatch_kind CHECK (kind IN ('scan', 'profile', 'extract'));

-- --------------------------------------------------------------------------- --
-- 2. La decision de promocion, persistida y reproducible
-- --------------------------------------------------------------------------- --

-- El artefacto sigue siendo inmutable: la decision es una fila aparte, no una
-- correccion de la fila de recepcion. Asi se puede volver a decidir cuando exista
-- un analizador nuevo, sin reescribir lo que paso.
CREATE TABLE fincilia.promotion_decision (
  decision_id     uuid PRIMARY KEY,
  company_id      uuid NOT NULL REFERENCES fincilia.company(company_id),
  artifact_id     uuid NOT NULL REFERENCES fincilia.source_artifact(artifact_id),
  run_id          uuid,
  decision        text NOT NULL
                    CHECK (decision IN ('promoted', 'quarantined', 'rejected')),
  reason_code     text NOT NULL CHECK (reason_code ~ '^[a-z][a-z0-9_]{2,79}$'),
  scanner_release text NOT NULL CHECK (length(scanner_release) BETWEEN 1 AND 40),
  media_type      text NOT NULL CHECK (length(media_type) BETWEEN 3 AND 120),
  internal_type   text NOT NULL DEFAULT '',
  findings        jsonb NOT NULL DEFAULT '[]'::jsonb,
  raw_object_key  text CHECK (raw_object_key IS NULL
                              OR length(raw_object_key) BETWEEN 1 AND 512),
  decided_at      timestamptz NOT NULL DEFAULT now(),
  -- Reproducible: el mismo escaner sobre el mismo artefacto es una sola decision.
  -- Reejecutarlo no crea una segunda ni cambia la primera, y por eso el reintento
  -- de un trabajo de escaneo es idempotente sin logica extra.
  CONSTRAINT uq_promotion_decision UNIQUE (artifact_id, scanner_release),
  -- Promovido y sin destino, o no promovido y con destino, serian dos formas de
  -- mentir sobre donde vive la evidencia.
  CONSTRAINT ck_promotion_key CHECK ((decision = 'promoted') = (raw_object_key IS NOT NULL)),
  -- Los hallazgos son metadatos: que se encontro y donde, jamas el valor.
  CONSTRAINT ck_promotion_findings CHECK (pg_column_size(findings) <= 16384)
);

CREATE INDEX idx_promotion_artifact
  ON fincilia.promotion_decision (artifact_id, decided_at DESC);

ALTER TABLE fincilia.promotion_decision ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.promotion_decision FORCE ROW LEVEL SECURITY;
CREATE POLICY promotion_decision_isolation ON fincilia.promotion_decision
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- Sin grant automatico que heredar: V0005 lo retiro. Cada verbo, explicito.
REVOKE ALL PRIVILEGES ON fincilia.promotion_decision FROM fincilia_app;
GRANT SELECT ON fincilia.promotion_decision TO fincilia_app;
-- El worker escanea y decide; no puede corregir una decision ya tomada.
GRANT SELECT, INSERT ON fincilia.promotion_decision TO fincilia_worker;
GRANT SELECT ON fincilia.promotion_decision TO fincilia_dispatch;

-- --------------------------------------------------------------------------- --
-- 3. La funcion de encolado admite el escaneo
-- --------------------------------------------------------------------------- --

-- La restriccion de la tabla y la validacion de la funcion son dos sitios donde
-- vive la misma lista, y V0007 solo habia tocado uno: encolar un escaneo fallaba
-- con «unknown work kind» aunque la tabla ya lo aceptara. Se corrige aqui, y una
-- prueba de extremo a extremo lo fija.
--
-- `CREATE OR REPLACE` conserva propietario y ACL, pero hay que ejecutarlo **como
-- el propietario**: el migrador no lo es, y `NOINHERIT` significa que no adquiere
-- sus derechos sin pedirlos.
GRANT CREATE ON SCHEMA fincilia TO fincilia_dispatch;
SET LOCAL ROLE fincilia_dispatch;

CREATE OR REPLACE FUNCTION fincilia.enqueue_processing_run(
  p_company_id uuid, p_artifact_id uuid, p_kind text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, fincilia
AS $enqueue$
DECLARE
  v_run_id  uuid;
  v_version integer;
BEGIN
  IF p_kind IS NULL OR p_kind NOT IN ('scan', 'profile', 'extract') THEN
    RAISE EXCEPTION 'unknown work kind' USING ERRCODE = '22023';
  END IF;
  IF p_company_id IS NULL
     OR p_company_id::text IS DISTINCT FROM current_setting('fincilia.company_id', true) THEN
    RAISE EXCEPTION 'the requested company does not match the authorised context'
      USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM fincilia.source_artifact a
                  WHERE a.artifact_id = p_artifact_id
                    AND a.company_id = p_company_id) THEN
    RAISE EXCEPTION 'no such artifact in this context' USING ERRCODE = '42501';
  END IF;

  SELECT v.version INTO v_version
    FROM fincilia.authorization_version v
   WHERE v.company_id = p_company_id;
  IF v_version IS NULL THEN
    RAISE EXCEPTION 'company has no authorization version' USING ERRCODE = '42501';
  END IF;

  v_run_id := gen_random_uuid();
  INSERT INTO fincilia.processing_run (run_id, company_id, artifact_id, kind,
                                       authorization_version)
  VALUES (v_run_id, p_company_id, p_artifact_id, p_kind, v_version)
  ON CONFLICT (company_id, artifact_id, kind) WHERE status IN ('queued', 'running')
  DO NOTHING
  RETURNING processing_run.run_id INTO v_run_id;

  IF v_run_id IS NULL THEN
    SELECT r.run_id INTO v_run_id FROM fincilia.processing_run r
     WHERE r.company_id = p_company_id AND r.artifact_id = p_artifact_id
       AND r.kind = p_kind AND r.status IN ('queued', 'running');
    IF v_run_id IS NULL THEN
      RAISE EXCEPTION 'conflicting work is not visible in this context'
        USING ERRCODE = '42501';
    END IF;
    RETURN v_run_id;
  END IF;

  INSERT INTO fincilia.dispatch_pointer (run_id, company_id, kind)
  VALUES (v_run_id, p_company_id, p_kind);
  RETURN v_run_id;
END;
$enqueue$;

ALTER FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text) OWNER TO fincilia_dispatch;
REVOKE ALL PRIVILEGES ON FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text) FROM PUBLIC;

-- El worker encola el perfilado cuando decide promover. Es la misma puerta que
-- usa la API, con las mismas validaciones: darle un INSERT directo sobre la cola
-- para esto seria deshacer justo lo que V0005 acaba de acotar.
GRANT EXECUTE ON FUNCTION fincilia.enqueue_processing_run(uuid, uuid, text)
  TO fincilia_worker;

RESET ROLE;
REVOKE CREATE ON SCHEMA fincilia FROM fincilia_dispatch;
