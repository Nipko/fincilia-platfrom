"""Pruebas de la especificacion de identidad, idempotencia y dedupe (FNC-DOM-007).

Materializa nueve de los doce escenarios que `docs/domain/idempotency-dedupe.json`
declara obligatorios. Los tres restantes —`TST-IDEM-001`, `TST-IDEM-004` y
`TST-IDEM-005`— exigen PostgreSQL real y quedan en FNC-DB-004; **no** se simulan aqui.

| Prueba | Invariante que ejecuta |
|---|---|
| `TST-DED-001` | reentrega exacta de un artefacto devuelve la version existente |
| `TST-DED-002` | dos transacciones legitimas identicas se conservan; nunca hay unicidad dura de negocio |
| `TST-DED-003` | periodos de extracto solapados conservan ambas observaciones |
| `TST-DED-004` | una reversion es una decision nueva que cita la previa |
| `TST-DED-005` | la similitud entre companias nunca produce candidato |
| `TST-IDEM-002` | misma clave y mismo payload devuelve lo existente |
| `TST-IDEM-003` | misma clave y otro payload es conflicto y senal de seguridad |
| `TST-IDEM-006` | un id de proveedor solo identifica dentro de su conexion |
| `TST-IDEM-007` | exactamente un dueno del reintento |

Ningun test depende de red, hora real, locale del host, orden de directorio ni Git.
"""

from __future__ import annotations

import copy
import re
import unittest
from decimal import Decimal
from pathlib import Path

from tools.dedupe_engine.engine import (
    FORBIDDEN_HARD_UNIQUE_FIELDS,
    RETRY_OWNER,
    IdentityError,
    artifact_identity,
    candidate_fingerprint,
    canonical_features,
    evaluate_candidate,
    inbox_transition,
    normalise_text,
    order_pair,
    provider_event_identity,
    redacts_raw_values,
    resolve_artifact,
    resolve_provider_event,
    retry_owners,
    validate_decision,
    validate_hard_uniqueness,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "tools/dedupe_engine"

SECRET = b"synthetic-laboratory-key-not-a-real-secret"
VERSIONS = {"secret_version": "v1", "locale_version": "es-CO-1", "rule_version": "r1"}
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def artifact(digest: str = DIGEST_A, raw: str = "raw-a", **overrides) -> dict:
    record = {
        "company_id": "company-alpha-synthetic",
        "data_source_id": "source-bank-synthetic",
        "content_sha256": digest,
        "raw_bytes_digest": raw,
    }
    record.update(overrides)
    return record


def movement(**overrides) -> dict:
    record = {
        "company_id": "company-alpha-synthetic",
        "movement_id": "movement-synthetic-1",
        "financial_account_id": "account-checking-synthetic",
        "occurrence_date": "2026-01-15",
        "posting_date": "2026-01-15",
        "amount": "150000.000000000000",
        "currency": "COP",
        "direction": "debit",
        "reference": "REF-SYNTHETIC-1",
        "counterparty": "counterparty-synthetic",
    }
    record.update(overrides)
    return record


MOVEMENT_RULE = {
    "id": "CAND-MOVEMENT-SIMILARITY",
    "layer": "economic_event",
    "features": ["company_id", "financial_account_id", "occurrence_date", "posting_date",
                 "amount", "currency", "direction", "reference", "counterparty"],
    "fingerprint_usage": "blocking_and_ranking_only",
    "unique_constraint_forbidden": True,
    "automatic_effect": "none",
}


def decision(**overrides) -> dict:
    record = {
        "decision_id": "decision-synthetic-1",
        "company_id": "company-alpha-synthetic",
        "candidate_id": "candidate-synthetic-1",
        "left_movement_id": "movement-synthetic-1",
        "right_movement_id": "movement-synthetic-2",
        "decision": "confirmed_same_event",
        "reason_code": "same_provider_reference",
        "evidence_refs": ["evidence-synthetic-1"],
        "decided_by": "subject-reviewer-synthetic",
        "decided_at": "2026-02-03",
        "rule_version": "r1",
        "engine_release_id": "engine-release-synthetic-0.1.0",
        "audit_event_id": "audit-synthetic-1",
    }
    record.update(overrides)
    return record


def codes(findings) -> set[str]:
    return {item.code for item in findings}


# --------------------------------------------------------------------------- #
# TST-DED-001 / TST-IDEM-002 / TST-IDEM-003
# --------------------------------------------------------------------------- #

class ArtifactIdentityTests(unittest.TestCase):
    def test_TST_DED_001_exact_redelivery_returns_the_existing_version(self) -> None:
        outcome = resolve_artifact(artifact(), artifact())
        self.assertEqual(outcome.action, "return_existing_artifact_version")
        self.assertFalse(outcome.security_signal)

    def test_TST_DED_001b_a_first_delivery_creates_a_version(self) -> None:
        self.assertEqual(resolve_artifact(None, artifact()).action,
                         "create_new_artifact_version")

    def test_TST_IDEM_002_same_key_same_payload_returns_what_exists(self) -> None:
        outcome = resolve_provider_event(
            {"connection_id": "connection-synthetic-1",
             "provider_event_id": "evt-1", "payload_digest": DIGEST_A},
            {"connection_id": "connection-synthetic-1",
             "provider_event_id": "evt-1", "payload_digest": DIGEST_A})
        self.assertEqual(outcome.action, "return_existing_receipt")

    def test_TST_IDEM_003_same_key_different_payload_is_a_security_signal(self) -> None:
        outcome = resolve_artifact(artifact(raw="raw-a"), artifact(raw="raw-b"))
        self.assertEqual(outcome.action, "conflict")
        self.assertTrue(outcome.security_signal)
        self.assertIn("IDM-IDENTITY-COLLISION", codes(outcome.findings))

    def test_TST_IDEM_003b_a_provider_payload_change_is_also_a_conflict(self) -> None:
        outcome = resolve_provider_event(
            {"connection_id": "connection-synthetic-1",
             "provider_event_id": "evt-1", "payload_digest": DIGEST_A},
            {"connection_id": "connection-synthetic-1",
             "provider_event_id": "evt-1", "payload_digest": DIGEST_B})
        self.assertEqual(outcome.action, "conflict")
        self.assertTrue(outcome.security_signal)

    def test_TST_DED_001c_identity_is_company_and_source_scoped(self) -> None:
        base = artifact_identity("company-alpha-synthetic", "source-bank-synthetic",
                                 DIGEST_A)
        other_company = artifact_identity("company-beta-synthetic",
                                          "source-bank-synthetic", DIGEST_A)
        other_source = artifact_identity("company-alpha-synthetic",
                                         "source-books-synthetic", DIGEST_A)
        self.assertNotEqual(base, other_company)
        self.assertNotEqual(base, other_source)

    def test_TST_DED_001d_a_malformed_digest_is_refused(self) -> None:
        for bad in ("not-a-digest", "", "a" * 63, "g" * 64):
            with self.subTest(bad=bad), self.assertRaises(IdentityError):
                artifact_identity("c", "s", bad)

    def test_TST_DED_001e_identity_without_company_or_source_is_refused(self) -> None:
        with self.assertRaises(IdentityError):
            artifact_identity("", "source-bank-synthetic", DIGEST_A)
        with self.assertRaises(IdentityError):
            artifact_identity("company-alpha-synthetic", "", DIGEST_A)

    def test_TST_IDEM_006_a_provider_id_only_identifies_inside_its_connection(self) -> None:
        first = provider_event_identity("connection-synthetic-1", "evt-1")
        second = provider_event_identity("connection-synthetic-2", "evt-1")
        self.assertNotEqual(first, second)
        outcome = resolve_provider_event(
            {"connection_id": "connection-synthetic-2", "provider_event_id": "evt-1",
             "payload_digest": DIGEST_B},
            {"connection_id": "connection-synthetic-1", "provider_event_id": "evt-1",
             "payload_digest": DIGEST_A})
        self.assertEqual(outcome.action, "accept_new_delivery")

    def test_TST_IDEM_006b_a_provider_id_without_a_connection_is_refused(self) -> None:
        with self.assertRaises(IdentityError):
            provider_event_identity("", "evt-1")
        with self.assertRaises(IdentityError):
            provider_event_identity("connection-synthetic-1", "")


# --------------------------------------------------------------------------- #
# TST-DED-002: unicidad dura prohibida
# --------------------------------------------------------------------------- #

class HardUniquenessTests(unittest.TestCase):
    def test_TST_DED_002_a_business_composite_is_refused(self) -> None:
        findings = validate_hard_uniqueness(
            ["company_id", "financial_account_id", "posting_date", "amount", "direction",
             "reference"])
        self.assertIn("IDM-BUSINESS-COMPOSITE", codes(findings))

    def test_TST_DED_002b_every_forbidden_field_is_caught_on_its_own(self) -> None:
        for forbidden in sorted(FORBIDDEN_HARD_UNIQUE_FIELDS):
            with self.subTest(field=forbidden):
                findings = validate_hard_uniqueness(["company_id", "id", forbidden])
                self.assertIn("IDM-BUSINESS-COMPOSITE", codes(findings))

    def test_TST_DED_002c_an_identity_based_constraint_is_accepted(self) -> None:
        self.assertEqual(validate_hard_uniqueness(["company_id", "id"]), [])
        self.assertEqual(
            validate_hard_uniqueness(["company_id", "data_source_id", "content_sha256"]),
            [])

    def test_TST_DED_002d_a_constraint_without_identity_is_refused(self) -> None:
        self.assertIn("IDM-NO-IDENTITY",
                      codes(validate_hard_uniqueness(["company_id", "currency"])))

    def test_TST_DED_002e_a_constraint_without_company_scope_is_refused(self) -> None:
        self.assertIn("IDM-COMPANY-SCOPE",
                      codes(validate_hard_uniqueness(["content_sha256"])))

    def test_TST_DED_002f_two_identical_legitimate_movements_both_survive(self) -> None:
        # Misma empresa, mismo dia, mismo importe, misma referencia: dos pagos
        # reales. Se levanta un candidato; ninguno se descarta.
        left = movement(movement_id="movement-synthetic-1")
        right = movement(movement_id="movement-synthetic-2")
        outcome = evaluate_candidate(left, right, MOVEMENT_RULE)
        self.assertTrue(outcome.raised)
        self.assertEqual(outcome.automatic_effect, "none")
        self.assertIn("preserved", outcome.reason)


# --------------------------------------------------------------------------- #
# TST-DED-003 / TST-DED-005: candidatos
# --------------------------------------------------------------------------- #

class CandidateTests(unittest.TestCase):
    def test_TST_DED_003_overlapping_statements_preserve_both_observations(self) -> None:
        rule = {
            "id": "CAND-SOURCE-OVERLAP", "layer": "source_observation",
            "features": ["company_id", "account_token", "provider_reference",
                         "posting_date", "amount", "direction"],
            "fingerprint_usage": "blocking_and_ranking_only",
            "automatic_effect": "none",
        }
        common = {"company_id": "company-alpha-synthetic",
                  "account_token": "token-synthetic-1",
                  "provider_reference": "PRV-1", "posting_date": "2026-01-15",
                  "amount": "150000.000000000000", "direction": "debit"}
        left = {**common, "movement_id": "observation-january", "source_locator": "page-3"}
        right = {**common, "movement_id": "observation-overlap", "source_locator": "page-1"}
        outcome = evaluate_candidate(left, right, rule)
        self.assertTrue(outcome.raised)
        self.assertEqual(outcome.automatic_effect, "none")

    def test_TST_DED_003b_a_differing_feature_raises_nothing(self) -> None:
        outcome = evaluate_candidate(
            movement(movement_id="movement-synthetic-1"),
            movement(movement_id="movement-synthetic-2", amount="150001.000000000000"),
            MOVEMENT_RULE)
        self.assertFalse(outcome.raised)
        self.assertIn("amount", outcome.reason)

    def test_TST_DED_005_cross_company_similarity_never_raises_a_candidate(self) -> None:
        outcome = evaluate_candidate(
            movement(movement_id="movement-synthetic-1"),
            movement(movement_id="movement-synthetic-2",
                     company_id="company-beta-synthetic"),
            MOVEMENT_RULE)
        self.assertFalse(outcome.raised)
        self.assertIn("IDM-COMPANY-SCOPE", codes(outcome.findings))

    def test_TST_DED_005b_a_movement_is_never_a_candidate_with_itself(self) -> None:
        same = movement()
        self.assertFalse(evaluate_candidate(same, copy.deepcopy(same),
                                            MOVEMENT_RULE).raised)

    def test_TST_DED_005c_a_rule_that_decides_automatically_is_refused(self) -> None:
        rule = {**MOVEMENT_RULE, "fingerprint_usage": "decides_identity"}
        outcome = evaluate_candidate(movement(movement_id="a"),
                                     movement(movement_id="b"), rule)
        self.assertIn("IDM-FINGERPRINT-USAGE", codes(outcome.findings))

    def test_TST_DED_005d_a_rule_without_features_raises_nothing(self) -> None:
        outcome = evaluate_candidate(movement(movement_id="a"),
                                     movement(movement_id="b"),
                                     {**MOVEMENT_RULE, "features": []})
        self.assertFalse(outcome.raised)
        self.assertIn("IDM-RULE-FEATURES", codes(outcome.findings))

    def test_TST_DED_005e_the_pair_order_does_not_depend_on_arrival(self) -> None:
        self.assertEqual(order_pair("b", "a"), order_pair("a", "b"))
        self.assertEqual(order_pair("a", "b"), ("a", "b"))


# --------------------------------------------------------------------------- #
# TST-DED-004: reversion de decision
# --------------------------------------------------------------------------- #

class DecisionTests(unittest.TestCase):
    def test_TST_DED_004_a_reversal_names_the_decision_it_reverses(self) -> None:
        prior = decision()
        reversal = decision(decision_id="decision-synthetic-2",
                            decision="confirmed_distinct",
                            decided_by="subject-second-reviewer-synthetic",
                            reverses_decision_id="decision-synthetic-1")
        self.assertEqual(validate_decision(reversal, prior), [])

    def test_TST_DED_004b_a_reversal_without_a_reference_is_refused(self) -> None:
        reversal = decision(decision_id="decision-synthetic-2",
                            decided_by="subject-second-reviewer-synthetic")
        self.assertIn("IDM-REVERSAL-REFERENCE",
                      codes(validate_decision(reversal, decision())))

    def test_TST_DED_004c_a_reversal_by_the_same_person_alone_is_refused(self) -> None:
        reversal = decision(decision_id="decision-synthetic-2",
                            reverses_decision_id="decision-synthetic-1")
        self.assertIn("IDM-REVERSAL-SOD", codes(validate_decision(reversal, decision())))

    def test_TST_DED_004d_a_reversal_pointing_elsewhere_is_refused(self) -> None:
        reversal = decision(decision_id="decision-synthetic-2",
                            decided_by="subject-second-reviewer-synthetic",
                            reverses_decision_id="decision-synthetic-99")
        self.assertIn("IDM-REVERSAL-REFERENCE",
                      codes(validate_decision(reversal, decision())))

    def test_TST_DED_004e_a_decision_never_deletes_a_movement_or_its_evidence(self) -> None:
        self.assertIn("IDM-NO-PHYSICAL-DELETE",
                      codes(validate_decision(decision(physically_deletes_movement=True))))
        self.assertIn("IDM-EVIDENCE-PRESERVED",
                      codes(validate_decision(decision(deletes_source_evidence=True))))

    def test_TST_DED_004f_every_required_field_is_demanded(self) -> None:
        for missing in ("company_id", "candidate_id", "decision", "reason_code",
                        "evidence_refs", "decided_by", "decided_at", "rule_version",
                        "engine_release_id", "audit_event_id"):
            with self.subTest(missing=missing):
                broken = decision()
                del broken[missing]
                self.assertIn("IDM-DECISION-FIELD", codes(validate_decision(broken)))

    def test_TST_DED_004g_an_unknown_decision_state_is_refused(self) -> None:
        self.assertIn("IDM-DECISION-STATE",
                      codes(validate_decision(decision(decision="probably_the_same"))))

    def test_TST_DED_004h_the_stored_pair_is_ordered(self) -> None:
        unordered = decision(left_movement_id="movement-synthetic-9",
                             right_movement_id="movement-synthetic-1")
        self.assertIn("IDM-PAIR-ORDER", codes(validate_decision(unordered)))


# --------------------------------------------------------------------------- #
# TST-IDEM-007: propiedad del reintento
# --------------------------------------------------------------------------- #

class RetryOwnershipTests(unittest.TestCase):
    def test_TST_IDEM_007_exactly_one_layer_owns_the_retry(self) -> None:
        owners, findings = retry_owners({RETRY_OWNER: True, "adapter": False,
                                         "circuit_breaker": False})
        self.assertEqual(owners, [RETRY_OWNER])
        self.assertEqual(findings, [])

    def test_TST_IDEM_007b_competing_layers_are_refused(self) -> None:
        _owners, findings = retry_owners({RETRY_OWNER: True, "adapter": True,
                                          "circuit_breaker": True})
        self.assertIn("IDM-RETRY-LAYERS", codes(findings))

    def test_TST_IDEM_007c_nobody_owning_the_retry_is_refused(self) -> None:
        _owners, findings = retry_owners({RETRY_OWNER: False, "adapter": False})
        self.assertIn("IDM-RETRY-OWNERLESS", codes(findings))

    def test_TST_IDEM_007d_the_wrong_single_owner_is_refused(self) -> None:
        _owners, findings = retry_owners({RETRY_OWNER: False, "adapter": True})
        self.assertIn("IDM-RETRY-OWNER", codes(findings))


# --------------------------------------------------------------------------- #
# Huella, normalizacion, inbox y privacidad
# --------------------------------------------------------------------------- #

class FingerprintAndInboxTests(unittest.TestCase):
    def features(self) -> dict:
        return {"amount": Decimal("150000.000000000000"), "reference": "REF-SYNTHETIC-1",
                "posting_date": "2026-01-15"}

    def test_fp_01_the_fingerprint_is_deterministic(self) -> None:
        first = candidate_fingerprint(self.features(), secret=SECRET, **VERSIONS)
        second = candidate_fingerprint(self.features(), secret=SECRET, **VERSIONS)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)

    def test_fp_02_rotating_any_version_changes_the_fingerprint(self) -> None:
        base = candidate_fingerprint(self.features(), secret=SECRET, **VERSIONS)
        for key in VERSIONS:
            with self.subTest(version=key):
                rotated = {**VERSIONS, key: VERSIONS[key] + "-next"}
                self.assertNotEqual(
                    base, candidate_fingerprint(self.features(), secret=SECRET, **rotated))

    def test_fp_03_rotating_the_key_changes_the_fingerprint(self) -> None:
        self.assertNotEqual(
            candidate_fingerprint(self.features(), secret=SECRET, **VERSIONS),
            candidate_fingerprint(self.features(), secret=b"another-synthetic-key",
                                  **VERSIONS))

    def test_fp_04_an_unkeyed_or_unversioned_fingerprint_is_refused(self) -> None:
        with self.assertRaises(IdentityError):
            candidate_fingerprint(self.features(), secret=b"", **VERSIONS)
        for key in VERSIONS:
            with self.subTest(missing=key), self.assertRaises(IdentityError):
                candidate_fingerprint(self.features(), secret=SECRET,
                                      **{**VERSIONS, key: ""})

    def test_fp_05_a_float_never_enters_a_fingerprint(self) -> None:
        with self.assertRaises(IdentityError):
            canonical_features({"amount": 150000.0}, "es-CO-1")

    def test_fp_06_normalisation_is_versioned_and_stable(self) -> None:
        self.assertEqual(normalise_text("  RÉF   Synthetic  ", "es-CO-1"),
                         normalise_text("réf synthetic", "es-CO-1"))
        with self.assertRaises(IdentityError):
            normalise_text("x", "")

    def test_fp_07_feature_order_does_not_change_the_fingerprint(self) -> None:
        forward = {"a": "1", "b": "2", "c": "3"}
        backward = {"c": "3", "b": "2", "a": "1"}
        self.assertEqual(canonical_features(forward, "es-CO-1"),
                         canonical_features(backward, "es-CO-1"))

    def test_inbox_01_a_terminal_state_never_reopens(self) -> None:
        for state in ("succeeded", "terminal_failed", "conflict"):
            with self.subTest(state=state):
                self.assertEqual(inbox_transition(state, "claim").action, "ignore")

    def test_inbox_02_a_stale_worker_cannot_write(self) -> None:
        outcome = inbox_transition("processing", "succeed", fencing_token=1,
                                   latest_token=2)
        self.assertEqual(outcome.action, "reject_stale_worker")
        self.assertIn("IDM-STALE-LEASE", codes(outcome.findings))

    def test_inbox_03_the_current_lease_holder_may_write(self) -> None:
        self.assertEqual(
            inbox_transition("processing", "succeed", fencing_token=2,
                             latest_token=2).action, "succeeded")

    def test_inbox_04_an_illegal_transition_is_rejected(self) -> None:
        self.assertEqual(inbox_transition("received", "succeed").action, "reject")

    def test_inbox_05_an_unknown_state_is_refused(self) -> None:
        with self.assertRaises(IdentityError):
            inbox_transition("almost_done", "claim")

    def test_priv_01_raw_business_values_never_reach_a_log(self) -> None:
        for key in ("amount", "reference", "counterparty", "description",
                    "account_number"):
            with self.subTest(key=key):
                self.assertIn("IDM-FINGERPRINT-PRIVACY",
                              codes(redacts_raw_values({key: "whatever"})))

    def test_priv_02_a_full_fingerprint_in_a_log_is_refused(self) -> None:
        self.assertIn("IDM-FINGERPRINT-PRIVACY",
                      codes(redacts_raw_values({"candidate_fingerprint": "a" * 64})))

    def test_priv_03_a_safe_log_record_passes(self) -> None:
        self.assertEqual(redacts_raw_values(
            {"company_id": "company-alpha-synthetic", "candidate_id": "candidate-1",
             "rule_version": "r1"}), [])


# --------------------------------------------------------------------------- #
# Disciplina del codigo y alcance declarado
# --------------------------------------------------------------------------- #

class SourceDisciplineTests(unittest.TestCase):
    def sources(self) -> list[Path]:
        return [path for path in sorted(SOURCE_DIR.glob("*.py"))
                if path.name != "test_engine.py"]

    def test_src_01_no_clock_network_randomness_or_shell(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            for token in ("import socket", "import urllib", "import requests",
                          "import random", "datetime.now(", "date.today(", "time.time(",
                          "import subprocess", "shell=True", "eval(", "exec(",
                          "os.environ"):
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_src_02_the_engine_never_uses_float(self) -> None:
        for source in self.sources():
            self.assertNotIn("float(", source.read_text(encoding="utf-8"), source.name)

    def test_src_03_no_anonymous_todo(self) -> None:
        pattern = re.compile(r"\b(TODO|FIXME)\b(?!\s*\(FNC-)")
        for source in self.sources():
            self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")),
                              source.name)

    def test_src_04_no_real_looking_secret_is_embedded(self) -> None:
        for source in self.sources():
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("SECRET =", text, source.name)
            self.assertIsNone(re.search(r"\b[0-9a-f]{40,}\b", text), source.name)

    def test_scope_01_the_three_database_bound_tests_are_not_faked_here(self) -> None:
        # TST-IDEM-001, 004 y 005 exigen PostgreSQL real: reclamo concurrente,
        # outbox tras commit y lease expirado. Se implementan en FNC-DB-004.
        implemented = {name for name in dir(self)}
        for absent in ("TST_IDEM_001", "TST_IDEM_004", "TST_IDEM_005"):
            self.assertFalse(any(absent in name for name in implemented),
                             f"{absent} needs real PostgreSQL and must not be simulated")


if __name__ == "__main__":
    unittest.main()
