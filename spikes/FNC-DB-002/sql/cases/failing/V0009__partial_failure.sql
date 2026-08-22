-- Migracion que falla a mitad. Crea un objeto y despues aborta.
-- Si la atomicidad funciona, `spike.partial_artifact` no debe existir despues,
-- y el historial no debe registrar V0009.

CREATE TABLE spike.partial_artifact (
  id integer PRIMARY KEY
);

INSERT INTO spike.partial_artifact (id) VALUES (1);

DO $fail$
BEGIN
  RAISE EXCEPTION 'FNC_SPIKE_DELIBERATE_FAILURE halfway through V0009';
END
$fail$;
