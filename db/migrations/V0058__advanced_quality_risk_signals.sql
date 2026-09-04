-- FNC-DQ-002: amplia el vocabulario cerrado de senales deterministicas.
-- Ningun codigo afirma fraude o concede efecto financiero.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE fincilia.quality_issue
  DROP CONSTRAINT quality_issue_rule_code_check;

ALTER TABLE fincilia.quality_issue
  ADD CONSTRAINT quality_issue_rule_code_check CHECK (rule_code IN (
    'dataset_completeness_mismatch',
    'dataset_completeness_unknown',
    'dataset_rejected_records',
    'lineage_invalidated',
    'duplicate_fingerprint',
    'reference_amount_conflict',
    'posting_delay_over_31_days',
    'amount_outlier_10x_median',
    'cross_dataset_duplicate_fingerprint',
    'reference_reuse_high_frequency',
    'same_day_same_amount_burst',
    'rapid_reversal_pair',
    'multiple_risk_indicators'
  ));

COMMENT ON CONSTRAINT quality_issue_rule_code_check ON fincilia.quality_issue IS
  'Closed vocabulary of quality/risk signals; none is proof of fraud.';
