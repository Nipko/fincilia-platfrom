-- FNC-ING-002: seleccion humana, inmutable y company-scoped de una hoja XLSX.
--
-- El libro ya fue inspeccionado y promovido antes de llegar aqui. Esta fila no
-- contiene celdas: fija cual identidad OPC puede usar el worker. Una seleccion
-- divergente no corrige la anterior; requiere otro artefacto/flujo explicito.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.source_artifact
  ADD CONSTRAINT uq_source_artifact_identity_company
  UNIQUE (artifact_id, company_id);

CREATE TABLE fincilia.spreadsheet_selection (
  selection_id       uuid PRIMARY KEY,
  company_id         uuid NOT NULL REFERENCES fincilia.company(company_id),
  artifact_id        uuid NOT NULL,
  workbook_identity  text NOT NULL
                       CHECK (workbook_identity ~ '^[0-9a-f]{64}$'),
  sheet_identity     text NOT NULL
                       CHECK (sheet_identity ~ '^[0-9a-f]{64}$'),
  sheet_name         text NOT NULL CHECK (length(sheet_name) BETWEEN 1 AND 120),
  sheet_ordinal      integer NOT NULL CHECK (sheet_ordinal BETWEEN 1 AND 1024),
  selected_by        uuid NOT NULL REFERENCES fincilia.subject(subject_id),
  selected_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_spreadsheet_selection_artifact UNIQUE (artifact_id),
  CONSTRAINT fk_spreadsheet_selection_artifact_company
    FOREIGN KEY (artifact_id, company_id)
    REFERENCES fincilia.source_artifact(artifact_id, company_id)
);

CREATE INDEX idx_spreadsheet_selection_company
  ON fincilia.spreadsheet_selection(company_id, selected_at DESC);

ALTER TABLE fincilia.spreadsheet_selection ENABLE ROW LEVEL SECURITY;
ALTER TABLE fincilia.spreadsheet_selection FORCE ROW LEVEL SECURITY;
CREATE POLICY spreadsheet_selection_isolation
  ON fincilia.spreadsheet_selection
  USING (company_id::text = current_setting('fincilia.company_id', true))
  WITH CHECK (company_id::text = current_setting('fincilia.company_id', true));

REVOKE ALL PRIVILEGES ON fincilia.spreadsheet_selection FROM PUBLIC;
REVOKE ALL PRIVILEGES ON fincilia.spreadsheet_selection FROM fincilia_app;
GRANT SELECT, INSERT ON fincilia.spreadsheet_selection TO fincilia_app;
GRANT SELECT ON fincilia.spreadsheet_selection TO fincilia_worker;

COMMENT ON TABLE fincilia.spreadsheet_selection IS
  'Eleccion inmutable de una hoja XLSX ya inspeccionada; no almacena valores.';
COMMENT ON COLUMN fincilia.spreadsheet_selection.sheet_identity IS
  'SHA-256 de sheetId, relationshipId y part OPC; no confia solo en el nombre.';
