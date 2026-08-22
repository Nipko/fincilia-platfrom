"""Pruebas de la especificacion ejecutable de completitud (FNC-DOM-006).

Materializa los seis escenarios que `docs/domain/completeness-balances.json` exige:

| Prueba | Invariante que ejecuta |
|---|---|
| `TST-CMP-001` | precedencia mismatch > unknown > verified; un control requerido sin evaluar es `unknown` |
| `TST-CMP-002` | `not_applicable` exige expectativa versionada con motivo |
| `TST-BAL-001` | formula del statement con Decimal exacto; solo cuentan los `confirmed` |
| `TST-BAL-002` | moneda unica, misma compania y mismo statement; un saldo de origen no prueba completitud |
| `TST-EXC-001` | excepcion aceptada: aprobador independiente, expiracion, sin auto-match, estado base preservado |
| `TST-CLOSE-001` | las nueve condiciones de cierre, conjuntivas y fail-closed |

Cada una degrada una entrada valida exactamente una vez. Ningun test depende de red,
hora real, locale, orden de directorio, Docker ni Git: la fecha entra como dato.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import re
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from tools.completeness_engine import cli as engine_cli
from tools.completeness_engine.engine import (
    CLOSE_CONDITIONS,
    MONEY_SCALE,
    MoneyError,
    apply_statement_exception,
    compute_statement,
    derive_assessment_state,
    evaluate_close_readiness,
    format_money,
    is_exact_zero,
    parse_money,
    validate_accepted_exception,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/golden/completeness"
SOURCE_DIR = ROOT / "tools/completeness_engine"
AS_OF = date(2026, 2, 5)


def run_cli(argv: list[str]) -> tuple[int, dict]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = engine_cli.main(argv)
    text = out.getvalue() or err.getvalue()
    return code, (json.loads(text) if text.strip() else {})


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def codes(findings) -> set[str]:
    return {item.code for item in findings}


def expectation(required=("record_count", "closing_balance"), not_applicable=()):
    return {
        "required_control_types": list(required),
        "not_applicable_controls": list(not_applicable),
    }


def control(control_type: str, outcome: str, required: bool = True) -> dict:
    return {"control_type": control_type, "outcome": outcome, "required": required}


def valid_exception(**overrides) -> dict:
    exception = {
        "scope": "source-bank-synthetic",
        "reason": "el extracto sintetico no publica saldo de apertura del periodo",
        "owner_subject_id": "subject-owner-synthetic",
        "approved_by": "subject-approver-synthetic",
        "approved_at": "2026-02-03",
        "materiality_policy_id": "materiality-synthetic-1",
        "valid_from": "2026-02-03",
        "expires_at": "2026-03-31",
        "allowed_actions": ["investigation", "disclosure"],
        "evidence_refs": ["evidence-synthetic-9"],
        "audit_event_id": "audit-synthetic-9",
        "disclosed_in_snapshot": True,
    }
    exception.update(overrides)
    return exception


# --------------------------------------------------------------------------- #
# Dinero
# --------------------------------------------------------------------------- #

class MoneyTests(unittest.TestCase):
    def test_money_01_a_float_is_refused_never_converted(self) -> None:
        for value in (1250000.0, 0.1, -3.5):
            with self.assertRaises(MoneyError):
                parse_money(value)

    def test_money_02_a_boolean_is_not_an_amount(self) -> None:
        with self.assertRaises(MoneyError):
            parse_money(True)

    def test_money_03_strings_and_integers_are_exact(self) -> None:
        self.assertEqual(parse_money("0.1") + parse_money("0.2"), parse_money("0.3"))
        self.assertEqual(parse_money(5), Decimal("5").quantize(parse_money("0")))

    def test_money_04_more_precision_than_the_canonical_scale_is_refused(self) -> None:
        with self.assertRaises(MoneyError):
            parse_money("1." + "0" * (MONEY_SCALE + 1) + "1")

    def test_money_05_infinite_and_nan_are_refused(self) -> None:
        for value in ("Infinity", "-Infinity", "NaN"):
            with self.assertRaises(MoneyError):
                parse_money(value)

    def test_money_06_the_canonical_form_is_never_scientific(self) -> None:
        self.assertEqual(format_money(parse_money("0")), "0." + "0" * MONEY_SCALE)
        self.assertNotIn("E", format_money(parse_money("0")))
        self.assertEqual(format_money(parse_money("1250000")),
                         "1250000." + "0" * MONEY_SCALE)

    def test_money_07_exact_zero_is_not_a_rounded_zero(self) -> None:
        self.assertTrue(is_exact_zero(parse_money("0")))
        self.assertFalse(is_exact_zero(parse_money("0.000000000001")))


# --------------------------------------------------------------------------- #
# TST-CMP-001 y TST-CMP-002
# --------------------------------------------------------------------------- #

class CompletenessDerivationTests(unittest.TestCase):
    def test_TST_CMP_001_mismatch_outranks_unknown_which_outranks_verified(self) -> None:
        every_match = [control("record_count", "match"), control("closing_balance", "match")]
        self.assertEqual(derive_assessment_state(every_match, expectation()).state,
                         "verified")

        with_unknown = [control("record_count", "match"),
                        control("closing_balance", "unknown")]
        self.assertEqual(derive_assessment_state(with_unknown, expectation()).state,
                         "unknown")

        # Un mismatch manda aunque haya un unknown: la precedencia no es "el peor
        # de los dos ultimos", es mismatch primero.
        with_both = [control("record_count", "mismatch"),
                     control("closing_balance", "unknown")]
        self.assertEqual(derive_assessment_state(with_both, expectation()).state,
                         "mismatch")

    def test_TST_CMP_001b_a_required_control_never_evaluated_is_unknown(self) -> None:
        # El control de saldo de cierre falta por completo. Sin esta regla, la
        # ausencia se leeria como verified.
        outcome = derive_assessment_state([control("record_count", "match")],
                                          expectation())
        self.assertEqual(outcome.state, "unknown")
        self.assertIn("CMP-CONTROL-MISSING", codes(outcome.findings))
        self.assertIn("closing_balance:absent", outcome.reasons)

    def test_TST_CMP_001c_an_optional_control_does_not_decide_the_state(self) -> None:
        outcome = derive_assessment_state(
            [control("record_count", "match"), control("closing_balance", "match"),
             control("page_section_coverage", "mismatch", required=False)],
            expectation())
        self.assertEqual(outcome.state, "verified")

    def test_TST_CMP_001d_an_unknown_outcome_value_is_never_a_pass(self) -> None:
        outcome = derive_assessment_state(
            [control("record_count", "probably_fine"),
             control("closing_balance", "match")], expectation())
        self.assertEqual(outcome.state, "unknown")
        self.assertIn("CMP-CONTROL-OUTCOME", codes(outcome.findings))

    def test_TST_CMP_002_not_applicable_needs_a_versioned_declaration(self) -> None:
        undeclared = derive_assessment_state(
            [control("record_count", "match"),
             control("closing_balance", "not_applicable")], expectation())
        self.assertEqual(undeclared.state, "unknown")
        self.assertIn("CMP-NOT-APPLICABLE", codes(undeclared.findings))

        declared = derive_assessment_state(
            [control("record_count", "match"),
             control("closing_balance", "not_applicable")],
            expectation(not_applicable=[{
                "control_type": "closing_balance",
                "reason": "el extracto sintetico no publica saldo de cierre",
                "expectation_version": "expectation-synthetic-2"}]))
        self.assertEqual(declared.state, "verified")
        self.assertEqual(declared.findings, [])

    def test_TST_CMP_002b_a_declaration_without_reason_or_version_is_refused(self) -> None:
        for partial in ({"control_type": "closing_balance", "reason": "porque si"},
                        {"control_type": "closing_balance",
                         "expectation_version": "expectation-synthetic-2"}):
            with self.subTest(partial=sorted(partial)):
                outcome = derive_assessment_state(
                    [control("record_count", "match"),
                     control("closing_balance", "not_applicable")],
                    expectation(not_applicable=[partial]))
                self.assertEqual(outcome.state, "unknown")
                self.assertIn("CMP-NOT-APPLICABLE", codes(outcome.findings))

    def test_TST_CMP_002c_derivation_is_deterministic(self) -> None:
        controls = [control("record_count", "unknown"), control("closing_balance", "match")]
        first = derive_assessment_state(controls, expectation()).as_dict()
        second = derive_assessment_state(controls, expectation()).as_dict()
        self.assertEqual(first, second)

    def test_TST_CMP_002d_a_control_without_a_type_is_never_silently_skipped(self) -> None:
        outcome = derive_assessment_state(
            [{"outcome": "match", "required": True},
             control("record_count", "match"), control("closing_balance", "match")],
            expectation())
        self.assertEqual(outcome.state, "unknown")
        self.assertIn("CMP-CONTROL-TYPE", codes(outcome.findings))


# --------------------------------------------------------------------------- #
# TST-BAL-001 y TST-BAL-002
# --------------------------------------------------------------------------- #

class BalanceTests(unittest.TestCase):
    def setUp(self) -> None:
        document = load("statement_balanced.json")
        self.statement = document["statement"]
        self.items = document["items"]
        self.expected = document["expected"]

    def test_TST_BAL_001_the_formula_uses_exact_decimal_and_only_confirmed_items(self) -> None:
        outcome = compute_statement(self.statement, self.items)
        self.assertEqual(outcome.state, "balanced")
        self.assertEqual(format_money(outcome.adjusted_bank_balance),
                         self.expected["adjusted_bank_balance"])
        self.assertEqual(format_money(outcome.unexplained_difference),
                         self.expected["unexplained_difference"])
        self.assertEqual(sorted(outcome.counted_item_ids),
                         self.expected["counted_item_ids"])
        # El item propuesto vale 500000 y no entra: si contara, el statement no cuadraria.
        self.assertEqual(sorted(outcome.ignored_item_ids),
                         self.expected["ignored_item_ids"])

    def test_TST_BAL_001b_a_proposed_item_never_moves_the_balance(self) -> None:
        promoted = copy.deepcopy(self.items)
        promoted[2]["state"] = "confirmed"
        promoted[2].update(approved_by="subject-approver-synthetic",
                           approved_at="2026-02-03",
                           sod_check="prepared_by_differs_from_approved_by",
                           evidence_refs=["evidence-synthetic-3"])
        outcome = compute_statement(self.statement, promoted)
        self.assertNotEqual(outcome.state, "balanced")
        self.assertEqual(format_money(outcome.unexplained_difference),
                         "500000." + "0" * MONEY_SCALE)

    def test_TST_BAL_001c_balanced_requires_an_exact_zero(self) -> None:
        drifted = copy.deepcopy(self.statement)
        drifted["books_closing_balance"] = "1179999.999999999999"
        outcome = compute_statement(drifted, self.items)
        self.assertEqual(outcome.state, "review_required")
        self.assertFalse(is_exact_zero(outcome.unexplained_difference))

    def test_TST_BAL_001d_a_float_amount_is_refused_not_rounded(self) -> None:
        floated = copy.deepcopy(self.items)
        floated[0]["amount"] = 90000.0
        outcome = compute_statement(self.statement, floated)
        self.assertIn("BAL-MONEY", codes(outcome.findings))
        self.assertEqual(outcome.state, "review_required")

    def test_TST_BAL_001e_a_confirmed_item_without_evidence_or_sod_is_refused(self) -> None:
        for missing in ("approved_by", "approved_at", "sod_check", "evidence_refs"):
            with self.subTest(missing=missing):
                broken = copy.deepcopy(self.items)
                del broken[0][missing]
                outcome = compute_statement(self.statement, broken)
                self.assertIn("BAL-CONFIRMED-EVIDENCE", codes(outcome.findings))

    def test_TST_BAL_001f_whoever_prepared_an_item_cannot_approve_it(self) -> None:
        broken = copy.deepcopy(self.items)
        broken[0]["approved_by"] = broken[0]["prepared_by"]
        outcome = compute_statement(self.statement, broken)
        self.assertIn("BAL-SOD", codes(outcome.findings))

    def test_TST_BAL_002_a_foreign_currency_item_never_enters_the_statement(self) -> None:
        foreign = copy.deepcopy(self.items)
        foreign[0]["currency_code"] = "USD"
        outcome = compute_statement(self.statement, foreign)
        self.assertIn("BAL-CURRENCY", codes(outcome.findings))
        self.assertIn("item-synthetic-1", outcome.ignored_item_ids)

    def test_TST_BAL_002b_a_foreign_company_item_never_enters_the_statement(self) -> None:
        foreign = copy.deepcopy(self.items)
        foreign[0]["company_id"] = "company-beta-synthetic"
        outcome = compute_statement(self.statement, foreign)
        self.assertIn("BAL-COMPANY-SCOPE", codes(outcome.findings))
        self.assertIn("item-synthetic-1", outcome.ignored_item_ids)

    def test_TST_BAL_002c_an_item_of_another_statement_never_enters(self) -> None:
        foreign = copy.deepcopy(self.items)
        foreign[0]["statement_id"] = "statement-synthetic-9"
        outcome = compute_statement(self.statement, foreign)
        self.assertIn("BAL-STATEMENT-SCOPE", codes(outcome.findings))

    def test_TST_BAL_002d_the_amount_is_positive_and_the_side_carries_direction(self) -> None:
        negative = copy.deepcopy(self.items)
        negative[0]["amount"] = "-90000.000000000000"
        outcome = compute_statement(self.statement, negative)
        self.assertIn("BAL-AMOUNT-POSITIVE", codes(outcome.findings))

    def test_TST_BAL_002e_an_unknown_adjustment_side_is_refused(self) -> None:
        broken = copy.deepcopy(self.items)
        broken[0]["adjustment_side"] = "somewhere_else"
        outcome = compute_statement(self.statement, broken)
        self.assertIn("BAL-ADJUSTMENT-SIDE", codes(outcome.findings))

    def test_TST_BAL_002f_a_source_balance_alone_is_not_completeness(self) -> None:
        # Un statement que cuadra no dice nada sobre si la fuente estaba completa:
        # son preguntas distintas y el motor las mantiene separadas.
        outcome = compute_statement(self.statement, self.items)
        self.assertEqual(outcome.state, "balanced")
        assessment = derive_assessment_state([control("record_count", "unknown")],
                                             expectation())
        self.assertEqual(assessment.state, "unknown")

    def test_TST_BAL_002g_the_computation_is_deterministic(self) -> None:
        first = compute_statement(self.statement, self.items).as_dict()
        second = compute_statement(self.statement, self.items).as_dict()
        self.assertEqual(first, second)

    def test_TST_BAL_002h_reordering_items_does_not_change_the_result(self) -> None:
        shuffled = list(reversed(copy.deepcopy(self.items)))
        first = compute_statement(self.statement, self.items)
        second = compute_statement(self.statement, shuffled)
        self.assertEqual(first.adjusted_bank_balance, second.adjusted_bank_balance)
        self.assertEqual(first.unexplained_difference, second.unexplained_difference)
        self.assertEqual(sorted(first.counted_item_ids), sorted(second.counted_item_ids))


# --------------------------------------------------------------------------- #
# TST-EXC-001
# --------------------------------------------------------------------------- #

class AcceptedExceptionTests(unittest.TestCase):
    def test_TST_EXC_001_a_valid_exception_over_a_base_state_is_accepted(self) -> None:
        self.assertEqual(validate_accepted_exception(valid_exception(), "unknown", AS_OF),
                         [])

    def test_TST_EXC_001b_the_owner_cannot_approve_its_own_exception(self) -> None:
        broken = valid_exception(approved_by="subject-owner-synthetic")
        self.assertIn("EXC-INDEPENDENT-APPROVER",
                      codes(validate_accepted_exception(broken, "unknown", AS_OF)))

    def test_TST_EXC_001c_an_expired_exception_never_authorises_a_new_close(self) -> None:
        expired = valid_exception(expires_at="2026-01-31")
        self.assertIn("EXC-EXPIRED",
                      codes(validate_accepted_exception(expired, "unknown", AS_OF)))

    def test_TST_EXC_001d_an_exception_never_enables_auto_match(self) -> None:
        broken = valid_exception(allowed_actions=["investigation", "auto_match"])
        self.assertIn("EXC-AUTO-MATCH",
                      codes(validate_accepted_exception(broken, "unknown", AS_OF)))

    def test_TST_EXC_001e_the_base_state_is_preserved(self) -> None:
        broken = valid_exception(changes_base_state=True)
        self.assertIn("EXC-BASE-STATE",
                      codes(validate_accepted_exception(broken, "unknown", AS_OF)))

    def test_TST_EXC_001f_an_exception_only_applies_over_mismatch_or_unknown(self) -> None:
        self.assertIn("EXC-BASE-STATE",
                      codes(validate_accepted_exception(valid_exception(), "verified",
                                                        AS_OF)))

    def test_TST_EXC_001g_every_required_field_is_demanded(self) -> None:
        for missing in ("scope", "reason", "owner_subject_id", "approved_by",
                        "approved_at", "materiality_policy_id", "valid_from",
                        "expires_at", "allowed_actions", "evidence_refs",
                        "audit_event_id"):
            with self.subTest(missing=missing):
                broken = valid_exception()
                del broken[missing]
                self.assertIn("EXC-REQUIRED-FIELD",
                              codes(validate_accepted_exception(broken, "unknown", AS_OF)))

    def test_TST_EXC_001h_an_undisclosed_exception_is_refused(self) -> None:
        broken = valid_exception(disclosed_in_snapshot=False)
        self.assertIn("EXC-DISCLOSURE",
                      codes(validate_accepted_exception(broken, "unknown", AS_OF)))

    def test_TST_EXC_001i_a_difference_without_an_exception_is_never_balanced(self) -> None:
        document = load("statement_balanced.json")
        drifted = copy.deepcopy(document["statement"])
        drifted["books_closing_balance"] = "1000000.000000000000"
        outcome = apply_statement_exception(
            compute_statement(drifted, document["items"]), None, AS_OF)
        self.assertEqual(outcome.state, "review_required")
        self.assertIn("BAL-UNEXPLAINED", codes(outcome.findings))

    def test_TST_EXC_001j_a_valid_exception_moves_a_difference_to_exception_accepted(self) -> None:
        document = load("statement_balanced.json")
        drifted = copy.deepcopy(document["statement"])
        drifted["books_closing_balance"] = "1000000.000000000000"
        outcome = apply_statement_exception(
            compute_statement(drifted, document["items"]), valid_exception(), AS_OF)
        self.assertEqual(outcome.state, "exception_accepted")
        # La diferencia sigue ahi: la excepcion la divulga, no la borra.
        self.assertFalse(is_exact_zero(outcome.unexplained_difference))


# --------------------------------------------------------------------------- #
# TST-CLOSE-001
# --------------------------------------------------------------------------- #

class CloseReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.period = load("period_ready.json")

    def evaluate(self, period: dict):
        return evaluate_close_readiness(period, AS_OF)

    def test_TST_CLOSE_001_the_coherent_period_is_ready(self) -> None:
        outcome = self.evaluate(self.period)
        self.assertTrue(outcome.ready)
        self.assertEqual(outcome.unmet_conditions, [])
        self.assertEqual(outcome.state, "ready")

    def test_TST_CLOSE_001b_an_expected_source_without_assessment_blocks(self) -> None:
        period = copy.deepcopy(self.period)
        period["assessments"] = period["assessments"][:1]
        outcome = self.evaluate(period)
        self.assertFalse(outcome.ready)
        self.assertIn("every_expected_source_has_assessment", outcome.unmet_conditions)

    def test_TST_CLOSE_001c_an_unhandled_unknown_blocks(self) -> None:
        period = copy.deepcopy(self.period)
        period["assessments"][0]["state"] = "unknown"
        outcome = self.evaluate(period)
        self.assertFalse(outcome.ready)
        self.assertIn("no_unhandled_mismatch_or_unknown", outcome.unmet_conditions)

    def test_TST_CLOSE_001d_an_unknown_covered_by_a_valid_exception_closes(self) -> None:
        period = copy.deepcopy(self.period)
        period["assessments"][0]["state"] = "unknown"
        period["accepted_exceptions"] = [valid_exception()]
        outcome = self.evaluate(period)
        self.assertTrue(outcome.ready)
        self.assertEqual(outcome.state, "closed_with_disclosed_exception")

    def test_TST_CLOSE_001e_an_expired_exception_does_not_close(self) -> None:
        period = copy.deepcopy(self.period)
        period["assessments"][0]["state"] = "mismatch"
        period["accepted_exceptions"] = [valid_exception(expires_at="2026-01-15")]
        outcome = self.evaluate(period)
        self.assertFalse(outcome.ready)
        self.assertIn("EXC-EXPIRED", codes(outcome.findings))

    def test_TST_CLOSE_001f_a_missing_statement_blocks(self) -> None:
        period = copy.deepcopy(self.period)
        period["statements"] = []
        outcome = self.evaluate(period)
        self.assertIn("statement_for_every_required_account_and_currency",
                      outcome.unmet_conditions)

    def test_TST_CLOSE_001g_a_balanced_label_with_a_difference_blocks(self) -> None:
        period = copy.deepcopy(self.period)
        period["statements"][0]["unexplained_difference"] = "0.000000000001"
        outcome = self.evaluate(period)
        self.assertFalse(outcome.ready)
        self.assertIn("every_statement_balanced_or_explicit_exception_accepted",
                      outcome.unmet_conditions)
        self.assertIn("no_hidden_unexplained_difference", outcome.unmet_conditions)

    def test_TST_CLOSE_001h_a_confirmed_item_without_evidence_or_sod_blocks(self) -> None:
        for missing in ("evidence_refs", "sod_check"):
            with self.subTest(missing=missing):
                period = copy.deepcopy(self.period)
                del period["confirmed_items"][0][missing]
                self.assertIn("confirmed_items_have_evidence_and_sod",
                              self.evaluate(period).unmet_conditions)

    def test_TST_CLOSE_001i_a_published_field_without_lineage_blocks(self) -> None:
        period = copy.deepcopy(self.period)
        del period["published_fields"][0]["lineage_ref"]
        self.assertIn("all_published_fields_and_decisions_have_lineage",
                      self.evaluate(period).unmet_conditions)

    def test_TST_CLOSE_001j_a_floating_version_blocks(self) -> None:
        for key in ("engine_release_id", "canonical_schema_version", "rule_version"):
            for value in ("latest", "main", ""):
                with self.subTest(key=key, value=value):
                    period = copy.deepcopy(self.period)
                    period["fixed_versions"][key] = value
                    self.assertIn("engine_schema_reference_and_rule_versions_fixed",
                                  self.evaluate(period).unmet_conditions)

    def test_TST_CLOSE_001k_authorization_must_be_revalidated(self) -> None:
        period = copy.deepcopy(self.period)
        period["authorization_revalidated_before_snapshot"] = False
        self.assertIn("authorization_revalidated_before_snapshot",
                      self.evaluate(period).unmet_conditions)

    def test_TST_CLOSE_001l_match_coverage_is_never_completeness(self) -> None:
        period = copy.deepcopy(self.period)
        period["matching_coverage_offered_as_completeness"] = True
        outcome = self.evaluate(period)
        self.assertFalse(outcome.ready)
        self.assertIn("CLOSE-MATCHING-NOT-COMPLETENESS", codes(outcome.findings))

    def test_TST_CLOSE_001m_the_nine_conditions_are_exactly_the_contract_ones(self) -> None:
        contract = json.loads(
            (ROOT / "docs/domain/completeness-balances.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(CLOSE_CONDITIONS),
                         sorted(contract["close_readiness_gate"]["required_conditions"]))

    def test_TST_CLOSE_001n_the_evaluation_is_deterministic(self) -> None:
        self.assertEqual(self.evaluate(self.period).as_dict(),
                         self.evaluate(self.period).as_dict())


# --------------------------------------------------------------------------- #
# CLI, fixtures y disciplina del codigo
# --------------------------------------------------------------------------- #

class CliAndFixtureTests(unittest.TestCase):
    def test_cli_01_the_balanced_fixture_matches_its_declared_expectation(self) -> None:
        code, payload = run_cli(["statement",
                                 "tests/golden/completeness/statement_balanced.json"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["mismatches"], {})

    def test_cli_02_the_ready_period_closes(self) -> None:
        code, payload = run_cli(["close", "tests/golden/completeness/period_ready.json"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["ready"])

    def test_cli_03_a_traversing_or_absolute_fixture_is_refused(self) -> None:
        for candidate in ("../outside.json", "/etc/passwd", "C:/Windows/win.ini",
                          "tests/../../outside.json"):
            with self.subTest(candidate=candidate):
                code, _ = run_cli(["statement", candidate])
                self.assertEqual(code, 2)

    def test_cli_04_a_missing_fixture_is_invalid_usage(self) -> None:
        code, _ = run_cli(["close", "tests/golden/completeness/absent.json"])
        self.assertEqual(code, 2)

    def test_cli_05_fixtures_are_listed_and_declared_synthetic(self) -> None:
        code, payload = run_cli(["fixtures"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["data_classification"], "synthetic_only")
        self.assertGreaterEqual(payload["count"], 2)

    def test_fix_01_no_fixture_carries_anything_that_looks_real(self) -> None:
        patterns = {
            "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            "nit": re.compile(r"\b\d{9}-\d\b"),
            "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,}\b"),
        }
        for path in sorted(FIXTURES.glob("*.json")):
            text = path.read_text(encoding="utf-8")
            self.assertIn("synthetic", text, path.name)
            for name, pattern in patterns.items():
                self.assertIsNone(pattern.search(text), f"{path.name}: {name}")

    def test_fix_02_every_fixture_amount_is_a_string_never_a_json_number(self) -> None:
        for path in sorted(FIXTURES.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))

            def walk(node, where: str) -> None:
                if isinstance(node, dict):
                    for key, value in node.items():
                        if key in ("amount", "bank_closing_balance",
                                   "books_closing_balance", "unexplained_difference",
                                   "adjusted_bank_balance"):
                            self.assertIsInstance(value, str, f"{where}.{key}")
                        walk(value, f"{where}.{key}")
                elif isinstance(node, list):
                    for index, item in enumerate(node):
                        walk(item, f"{where}[{index}]")

            walk(document, path.name)

    def test_src_01_the_engine_never_reaches_the_clock_network_or_randomness(self) -> None:
        forbidden = ("import socket", "import urllib", "import requests", "import random",
                     "datetime.now(", "date.today(", "datetime.utcnow(", "time.time(",
                     "import subprocess", "shell=True", "eval(", "exec(", "os.environ")
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_engine.py":
                continue
            text = source.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{source.name}: {token}")

    def test_src_02_the_engine_never_uses_float(self) -> None:
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_engine.py":
                continue
            text = source.read_text(encoding="utf-8")
            self.assertNotIn("float(", text, source.name)

    def test_src_03_no_anonymous_todo(self) -> None:
        pattern = re.compile(r"\b(TODO|FIXME)\b(?!\s*\(FNC-)")
        for source in sorted(SOURCE_DIR.glob("*.py")):
            if source.name == "test_engine.py":
                continue
            self.assertIsNone(pattern.search(source.read_text(encoding="utf-8")),
                              source.name)


if __name__ == "__main__":
    unittest.main()
