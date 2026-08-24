-- V0003: evidencia de origen y cola de procesamiento.
--
-- Un `source_artifact` es un hecho: unos bytes concretos llegaron a una empresa
-- en un momento concreto. Por eso la fila es **inmutable**: el rol runtime puede
-- insertarla y leerla, nunca corregirla ni borrarla. Corregir un artefacto seria
-- reescribir la evidencia sobre la que se sostiene un cierre.
--
-- La clave es el contenido, no el nombre. Dos subidas de los mismos bytes son la
-- misma entrega, aunque el fichero se llame distinto; y el mismo nombre con
-- bytes distintos son dos entregas. `UNIQUE (company_id, content_sha256)` dice
-- exactamente eso, y hace la subida idempotente sin necesidad de que el cliente
-- mande una clave de idempotencia que puede equivocarse.
--
-- Bytes identicos prueban la misma entrega, **no** el mismo hecho economico. Que
-- dos ficheros iguales representen dos pagos reales distintos es un problema del
-- dominio, no del almacenamiento, y no se resuelve aqui.

-- --------------------------------------------------------------------------- --
-- Artefactos de origen
-- --------------------------------------------------------------------------- --

CREATE TABLE fincilia.source_artifact (
  artifact_id    uuid PRIMARY KEY,
  company_id     uuid NOT NULL REFERENCES fincilia.company(company_id),
  filename       text NOT NULL CHECK (length(filename) BETWEEN 1 AND 255),
  byte_size      bigint NOT NULL CHECK (byte_size > 0),
  content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  media_type     text NOT NULL CHECK (length(media_type) BETWEEN 3 AND 120),
  zone           text NOT NULL CHECK (zone IN ('quarantine', 'raw')),
  object_key     text NOT NULL CHECK (length(object_key) BETWEEN 1 AND 512),
  status         text NOT NULL CHECK (status IN ('stored', 'quarantined')),
  findings       jsonb NOT NULL DEFAULT '[]'::jsonb,
  uploaded_by    uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  uploaded_at    timestamptz NOT NULL DEFAULT now(),
  -- Los mismos bytes en la misma empresa son la misma entrega.
  CONSTRAINT uq_artifact_content UNIQUE (company_id, content_sha256),
  -- Un artefacto en cuarentena no puede declararse almacenado, ni al reves: si
  -- la zona y el estado pudieran discrepar, «esta en raw» dejaria de significar
  -- «paso la admision».
  CONSTRAINT ck_artifact_zone_status CHECK (
    (zone = 'raw' AND status = 'stored')
    OR (zone = 'quarantine' AND status = 'quarantined')),
  -- Los hallazgos son metadatos: que se encontro y donde, nunca el valor.
  CONSTRAINT ck_artifact_findings_bounded CHECK (pg_column_size(findings) <= 16384)
);

CREATE INDEX idx_artifact_company_time
  ON fincilia.source_artifact (company_id, uploaded_at DESC);

-- --------------------------------------------------------------------------- --
-- Cola de procesamiento
-- --------------------------------------------------------------------------- --

-- Cola persistente y simple. Vive en PostgreSQL a proposito: el estado de un
-- trabajo que sostiene evidencia financiera no puede depender de una cache que
-- se puede perder. La interfaz es lo bastante estrecha como para sustituirla mas
-- adelante por un motor de workflows sin tocar el dominio.
CREATE TABLE fincilia.processing_run (
  run_id      uuid PRIMARY KEY,
  company_id  uuid NOT NULL REFERENCES fincilia.company(company_id),
  artifact_id uuid NOT NULL REFERENCES fincilia.source_artifact(artifact_id),
  kind        text NOT NULL CHECK (kind IN ('profile', 'extract')),
  status      text NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  attempt     integer NOT NULL DEFAULT 1 CHECK (attempt BETWEEN 1 AND 10),
  queued_at   timestamptz NOT NULL DEFAULT now(),
  started_at  timestamptz,
  finished_at timestamptz,
  result      jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_code  text CHECK (error_code IS NULL OR length(error_code) BETWEEN 1 AND 80),
  CONSTRAINT uq_run_attempt UNIQUE (artifact_id, kind, attempt),
  -- Un trabajo terminado tiene principio y fin, y el fin no precede al principio.
  CONSTRAINT ck_run_timeline CHECK (
    (status = 'queued' AND started_at IS NULL AND finished_at IS NULL)
    OR (status = 'running' AND started_at IS NOT NULL AND finished_at IS NULL)
    OR (status IN ('succeeded', 'failed') AND started_at IS NOT NULL
        AND finished_at IS NOT NULL AND finished_at >= started_at)),
  -- Fallar sin decir por que deja al operador adivinando; tener exito con un
  -- codigo de error deja al lector sin saber a cual creer.
  CONSTRAINT ck_run_error CHECK (
    (status = 'failed' AND error_code IS NOT NULL)
    OR (status <> 'failed' AND error_code IS NULL)),
  CONSTRAINT ck_run_result_bounded CHECK (pg_column_size(result) <= 65536)
);

CREATE INDEX idx_run_pending
  ON fincilia.processing_run (company_id, queued_at)
  WHERE status = 'queued';

-- --------------------------------------------------------------------------- --
-- Row Level Security
-- --------------------------------------------------------------------------- --

ALTER TABLE fincilia.source_artifact ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.source_artifact FORCE ROW LEVEL SECURITY;
CREATE POLICY source_artifact_isolation ON fincilia.source_artifact
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.processing_run ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.processing_run FORCE ROW LEVEL SECURITY;
CREATE POLICY processing_run_isolation ON fincilia.processing_run
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- --------------------------------------------------------------------------- --
-- Privilegios
-- --------------------------------------------------------------------------- --

-- Insertar y leer. **No** actualizar ni borrar: un artefacto es un hecho, y los
-- hechos no se corrigen, se suceden.
GRANT SELECT, INSERT ON fincilia.source_artifact TO fincilia_app;
-- `ALTER DEFAULT PRIVILEGES` de V0001 concede UPDATE a toda tabla nueva del
-- esquema. Aqui hay que quitarlo a mano: un privilegio heredado por defecto es
-- justo el que nadie recuerda revisar.
REVOKE UPDATE, DELETE ON fincilia.source_artifact FROM fincilia_app;

-- Un trabajo si cambia de estado mientras corre, asi que aqui si hay UPDATE.
GRANT SELECT, INSERT, UPDATE ON fincilia.processing_run TO fincilia_app;
