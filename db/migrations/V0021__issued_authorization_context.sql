-- V0021: capabilities persistentes con alcance de autorizacion inmutable.
--
-- Una sesion HTTP corta sigue revalidandose en linea y no crea una fila aqui.
-- Esta entidad existe para trabajo que sobrevive a una peticion: jobs, exports
-- programados, enlaces y schedules. La referencia del recurso y la clave de
-- idempotencia llegan como HMAC; nunca se persiste el valor que recibio la API.

-- El FK compuesto impide que una fila combine la empresa de un engagement con
-- la firma de otro. Company sigue siendo la frontera estable.
CREATE UNIQUE INDEX uq_engagement_scoped_identity
  ON fincilia.engagement (company_id, firm_id, engagement_id);

CREATE TABLE fincilia.issued_authorization_context (
  context_id               uuid PRIMARY KEY,
  company_id               uuid NOT NULL REFERENCES fincilia.company(company_id),
  subject_id               uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  firm_id                  uuid NOT NULL REFERENCES fincilia.firm(firm_id),
  engagement_id            uuid NOT NULL,
  purpose_code             text NOT NULL
                             CHECK (purpose_code IN (
                               'processing_job', 'dataset_export',
                               'report_export', 'shared_link',
                               'scheduled_capability'
                             )),
  resource_kind            text NOT NULL
                             CHECK (resource_kind ~ '^[a-z][a-z0-9_.-]{1,63}$'),
  resource_ref_digest      text NOT NULL
                             CHECK (resource_ref_digest ~ '^[0-9a-f]{64}$'),
  authorization_version    bigint NOT NULL CHECK (authorization_version >= 1),
  issued_at                timestamptz NOT NULL DEFAULT now(),
  expires_at               timestamptz NOT NULL,
  idempotency_key_digest   text NOT NULL
                             CHECK (idempotency_key_digest ~ '^[0-9a-f]{64}$'),
  issuance_digest          text NOT NULL
                             CHECK (issuance_digest ~ '^[0-9a-f]{64}$'),
  CONSTRAINT fk_issued_context_engagement_scope
    FOREIGN KEY (company_id, firm_id, engagement_id)
    REFERENCES fincilia.engagement(company_id, firm_id, engagement_id),
  CONSTRAINT ck_issued_context_window
    CHECK (
      expires_at > issued_at
      AND expires_at <= issued_at + interval '30 days'
    ),
  CONSTRAINT uq_issued_context_idempotency
    UNIQUE (company_id, idempotency_key_digest),
  CONSTRAINT uq_issued_context_scoped_identity
    UNIQUE (company_id, context_id)
);

-- Revocar no reescribe lo emitido. Esta fila es el tombstone append-only que
-- corta una capability antes de que expire y conserva quien y por que lo hizo.
CREATE TABLE fincilia.issued_authorization_revocation (
  company_id    uuid NOT NULL,
  context_id    uuid NOT NULL,
  revoked_by    uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  reason_code   text NOT NULL
                  CHECK (reason_code IN (
                    'access_removed', 'engagement_changed',
                    'security_response', 'resource_retired',
                    'superseded'
                  )),
  revoked_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, context_id),
  CONSTRAINT fk_issued_revocation_context_scope
    FOREIGN KEY (company_id, context_id)
    REFERENCES fincilia.issued_authorization_context(company_id, context_id)
);

ALTER TABLE fincilia.issued_authorization_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.issued_authorization_context FORCE ROW LEVEL SECURITY;
CREATE POLICY issued_authorization_context_isolation
  ON fincilia.issued_authorization_context
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

ALTER TABLE fincilia.issued_authorization_revocation ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.issued_authorization_revocation FORCE ROW LEVEL SECURITY;
CREATE POLICY issued_authorization_revocation_isolation
  ON fincilia.issued_authorization_revocation
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

-- V0001 concede UPDATE por defecto a tablas nuevas. Se retira explicitamente:
-- tanto el contexto como su revocacion son registros append-only para runtime.
REVOKE ALL ON fincilia.issued_authorization_context FROM PUBLIC, fincilia_app;
REVOKE ALL ON fincilia.issued_authorization_revocation FROM PUBLIC, fincilia_app;
GRANT SELECT, INSERT ON fincilia.issued_authorization_context TO fincilia_app;
GRANT SELECT, INSERT ON fincilia.issued_authorization_revocation TO fincilia_app;

COMMENT ON TABLE fincilia.issued_authorization_context IS
  'Capability de larga vida: alcance inmutable, referencia HMAC y revalidacion online.';
COMMENT ON TABLE fincilia.issued_authorization_revocation IS
  'Tombstone append-only que revoca una capability sin reescribir su emision.';
