-- FNC-ING-007: el migrador conserva mantenimiento bajo FORCE RLS.
-- La aplicación continúa sin privilegios ni política sobre esta tabla.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

CREATE POLICY pdf_ocr_result_migrator_maintenance
  ON fincilia.pdf_ocr_result
  TO fincilia_migrator
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

COMMENT ON POLICY pdf_ocr_result_migrator_maintenance
  ON fincilia.pdf_ocr_result IS
  'Permite migración, retención y restauración solo con contexto de empresa.';
