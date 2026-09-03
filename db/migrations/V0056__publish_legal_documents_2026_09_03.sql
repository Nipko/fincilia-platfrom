-- V0056: publica las versiones visibles de terminos y privacidad del 2026-09-03.
--
-- Las aceptaciones historicas permanecen intactas. Solo el alta nueva puede
-- aceptar las versiones activas; cambiar el texto nunca reescribe evidencia.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

SET LOCAL ROLE fincilia_identity;

UPDATE fincilia.legal_document_version
SET active_for_registration = false
WHERE document_kind IN ('terms', 'privacy')
  AND active_for_registration;

INSERT INTO fincilia.legal_document_version (
  document_kind, document_version, published_at, active_for_registration
) VALUES
  ('terms', 'terms-2026-09-03', '2026-09-03T00:00:00Z', true),
  ('privacy', 'privacy-2026-09-03', '2026-09-03T00:00:00Z', true);

RESET ROLE;
