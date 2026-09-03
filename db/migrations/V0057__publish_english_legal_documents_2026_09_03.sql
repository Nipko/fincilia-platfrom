-- V0057: publishes the English legal documents used by new registrations.
--
-- Existing versions and acceptances remain immutable evidence. The optional
-- ISO-639-1 suffix makes the publication language explicit without changing
-- the stable document kind or accepting an unversioned policy.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

SET LOCAL ROLE fincilia_identity;

ALTER TABLE fincilia.legal_document_version
  DROP CONSTRAINT legal_document_version_document_version_check;

ALTER TABLE fincilia.legal_document_version
  ADD CONSTRAINT legal_document_version_document_version_check
  CHECK (
    document_version ~ '^[a-z]+-[0-9]{4}-[0-9]{2}-[0-9]{2}(-[a-z]{2})?$'
  ) NOT VALID;

ALTER TABLE fincilia.legal_document_version
  VALIDATE CONSTRAINT legal_document_version_document_version_check;

UPDATE fincilia.legal_document_version
SET active_for_registration = false
WHERE document_kind IN ('terms', 'privacy')
  AND active_for_registration;

INSERT INTO fincilia.legal_document_version (
  document_kind, document_version, published_at, active_for_registration
) VALUES
  ('terms', 'terms-2026-09-03-en', '2026-09-03T19:45:00Z', true),
  ('privacy', 'privacy-2026-09-03-en', '2026-09-03T19:45:00Z', true);

COMMENT ON COLUMN fincilia.legal_document_version.document_version IS
  'Immutable publication identifier; optional final ISO-639-1 language suffix.';

RESET ROLE;
