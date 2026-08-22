-- V0003: paso EXPAND de expand/contract.
--
-- Se anade una columna nullable y sin default volatil. La version N de la
-- aplicacion sigue funcionando porque no la conoce, y la version N+1 puede
-- empezar a escribirla. El paso CONTRACT (hacerla NOT NULL o retirar la antigua)
-- pertenece a una release posterior y NO se ejecuta aqui: comprimir ambos pasos
-- en una sola release es justo lo que rompe la compatibilidad N/N+1.

ALTER TABLE spike.company_ledger
  ADD COLUMN external_reference text;

COMMENT ON COLUMN spike.company_ledger.external_reference IS
  'Paso expand. Nullable a proposito hasta que una release posterior haga contract.';
