-- V0004: puntero de despacho para el worker.
--
-- Un planificador que trabaja para varias empresas tiene un problema de arranque
-- en frio: para fijar el contexto de RLS necesita saber que empresa tiene trabajo
-- pendiente, y para saberlo necesitaria leer sin contexto. Con `FORCE ROW LEVEL
-- SECURITY` eso no devuelve nada, que es exactamente lo que debe pasar con las
-- tablas que llevan datos.
--
-- Las salidas posibles eran tres. Dar `BYPASSRLS` al worker: descartada, porque
-- convierte el aislamiento en una promesa. Una politica que abra
-- `processing_run` a un contexto especial: es lo mismo con otro nombre, y ademas
-- RLS es por fila, no por columna, asi que abriria la fila entera. La tercera es
-- esta: una tabla **aparte** que solo lleva identificadores y marcas de tiempo,
-- sin RLS y declarada como excepcion en `docs/database/migration-tooling.json`.
--
-- Lo que se filtra por esta via es «la empresa X tiene un trabajo pendiente». No
-- hay nombre de fichero, ni tipo, ni tamano, ni importe, ni sujeto. El validador
-- comprueba que las columnas siguen siendo exactamente las declaradas, para que
-- anadir aqui un dato de negocio no pueda pasar desapercibido.

CREATE TABLE fincilia.dispatch_pointer (
  run_id     uuid PRIMARY KEY REFERENCES fincilia.processing_run(run_id),
  company_id uuid NOT NULL,
  kind       text NOT NULL CHECK (kind IN ('profile', 'extract')),
  queued_at  timestamptz NOT NULL DEFAULT now(),
  claimed_at timestamptz,
  claimed_by text CHECK (claimed_by IS NULL OR length(claimed_by) BETWEEN 1 AND 80)
);

-- Solo los pendientes. El indice se queda pequeno aunque la tabla crezca.
CREATE INDEX idx_dispatch_pending
  ON fincilia.dispatch_pointer (queued_at)
  WHERE claimed_at IS NULL;

COMMENT ON TABLE fincilia.dispatch_pointer IS
  'Sin RLS a proposito: identificadores y marcas de tiempo, ningun dato de negocio. Excepcion declarada en docs/database/migration-tooling.json.';

-- El worker marca y borra su propio puntero; la fila de verdad vive en
-- `processing_run`, con RLS, y es la que decide si un trabajo se ejecuta.
GRANT SELECT, INSERT, UPDATE, DELETE ON fincilia.dispatch_pointer TO fincilia_app;
