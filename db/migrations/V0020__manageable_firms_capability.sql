-- V0020: lectura RLS minima de la firma propia antes de que exista una company.
--
-- V0005 retiro toda lectura de `firm` al runtime. No se devuelve acceso global:
-- la politica deja ver solo firmas donde el sujeto de sesion tiene membresia
-- activa. El migrador conserva su capacidad de bootstrap al no forzar RLS sobre
-- esta tabla global; el runtime nunca es propietario de ella.

ALTER TABLE fincilia.firm ENABLE ROW LEVEL SECURITY;

CREATE POLICY firm_active_membership_read ON fincilia.firm
  FOR SELECT
  TO fincilia_app
  USING (
    status = 'active'
    AND EXISTS (
      SELECT 1
        FROM fincilia.membership AS m
       WHERE m.firm_id = firm.firm_id
         AND m.subject_id::text = current_setting('fincilia.subject_id', true)
         AND m.status = 'active'
    )
  );

GRANT SELECT ON fincilia.firm TO fincilia_app;

COMMENT ON POLICY firm_active_membership_read ON fincilia.firm IS
  'Una persona solo ve firmas donde su membresia activa coincide con el contexto.';
