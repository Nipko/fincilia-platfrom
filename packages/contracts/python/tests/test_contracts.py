"""Pruebas de los contratos compartidos del producto.

Solo biblioteca estandar: se ejecutan sin levantar nada y sin instalar nada.

    python -m unittest discover -s packages/contracts/python

Incluye una prueba de acuerdo entre esta implementacion de producto y la
especificacion ejecutable de `tools/completeness_engine`. Que dos implementaciones
independientes coincidan sobre los mismos casos es lo unico que hace util tener
las dos; si divergen, una de las dos esta mal y hay que saberlo aqui.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY_ROOT / "packages/contracts/python"))
sys.path.insert(0, str(REPOSITORY_ROOT))

from fincilia_contracts.errors import problem  # noqa: E402
from fincilia_contracts.money import (  # noqa: E402
    MONEY_SCALE,
    ZERO,
    CurrencyError,
    MoneyError,
    add,
    format_money,
    is_exact_zero,
    parse_currency,
    parse_money,
    require_same_currency,
    subtract,
)
from fincilia_contracts.tenancy import (  # noqa: E402
    PERMISSIONS,
    ROLE_PERMISSIONS,
    ROLES,
    AuthorizationError,
    TenantContext,
    derive_permissions,
    violates_segregation,
)


def context(roles=("preparer",), **overrides) -> TenantContext:
    payload = {
        "subject_id": "subject-synthetic-1",
        "firm_id": "firm-synthetic-1",
        "company_id": "company-alpha-synthetic",
        "roles": tuple(roles),
        "authorization_version": 1,
    }
    payload.update(overrides)
    return TenantContext(**payload)


class MoneyTests(unittest.TestCase):
    def test_a_float_is_refused_never_converted(self) -> None:
        for value in (1250000.0, 0.1, -3.5, True):
            with self.subTest(value=value), self.assertRaises(MoneyError):
                parse_money(value)

    def test_exact_arithmetic(self) -> None:
        self.assertEqual(add(parse_money("0.1"), parse_money("0.2")), parse_money("0.3"))
        self.assertEqual(subtract(parse_money("1"), parse_money("1")), ZERO)

    def test_precision_beyond_the_canonical_scale_is_refused(self) -> None:
        with self.assertRaises(MoneyError):
            parse_money("1." + "0" * MONEY_SCALE + "1")

    def test_non_finite_money_is_refused(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(MoneyError):
                parse_money(value)

    def test_the_canonical_form_is_never_scientific(self) -> None:
        self.assertEqual(format_money(ZERO), "0." + "0" * MONEY_SCALE)
        self.assertNotIn("E", format_money(ZERO))

    def test_exact_zero_is_not_a_rounded_zero(self) -> None:
        self.assertTrue(is_exact_zero(parse_money("0")))
        self.assertFalse(is_exact_zero(parse_money("0.000000000001")))

    def test_currency_is_explicit_and_supported(self) -> None:
        self.assertEqual(parse_currency("cop"), "COP")
        for bad in ("", "   ", None, "XYZ", 42):
            with self.subTest(bad=bad), self.assertRaises(CurrencyError):
                parse_currency(bad)

    def test_mixing_currencies_is_refused(self) -> None:
        self.assertEqual(require_same_currency("COP", "COP"), "COP")
        with self.assertRaises(CurrencyError):
            require_same_currency("COP", "USD")

    def test_the_product_agrees_with_the_executable_specification(self) -> None:
        from tools.completeness_engine.engine import format_money as spec_format
        from tools.completeness_engine.engine import parse_money as spec_parse
        cases = ["0", "1", "-1", "0.000000000001", "1250000", "1180000.5",
                 "-99999999.123456789012"]
        for value in cases:
            with self.subTest(value=value):
                self.assertEqual(parse_money(value), spec_parse(value))
                self.assertEqual(format_money(parse_money(value)),
                                 spec_format(spec_parse(value)))
        for bad in (1.5, True, "NaN", "1." + "0" * MONEY_SCALE + "1"):
            with self.subTest(bad=bad):
                with self.assertRaises(Exception):
                    parse_money(bad)
                with self.assertRaises(Exception):
                    spec_parse(bad)


class TenancyTests(unittest.TestCase):
    def test_a_context_always_names_subject_firm_and_company(self) -> None:
        for missing in ("subject_id", "firm_id", "company_id"):
            with self.subTest(missing=missing), self.assertRaises(AuthorizationError):
                context(**{missing: ""})

    def test_an_unknown_role_is_refused(self) -> None:
        with self.assertRaises(AuthorizationError):
            context(roles=("superuser",))

    def test_authorization_version_starts_at_one(self) -> None:
        with self.assertRaises(AuthorizationError):
            context(authorization_version=0)

    def test_a_client_supplied_company_never_defines_the_scope(self) -> None:
        ctx = context()
        ctx.require_company("company-alpha-synthetic")
        with self.assertRaises(AuthorizationError):
            ctx.require_company("company-beta-synthetic")

    def test_a_missing_permission_is_denial_not_a_wildcard(self) -> None:
        ctx = context(roles=("read_only",))
        self.assertTrue(ctx.has("company.read"))
        self.assertFalse(ctx.has("match.confirm"))
        with self.assertRaises(AuthorizationError):
            ctx.require("match.confirm")

    def test_an_unknown_permission_is_refused_rather_than_ignored(self) -> None:
        with self.assertRaises(AuthorizationError):
            context(roles=("owner",)).require("anything.goes")

    def test_every_role_declares_only_known_permissions(self) -> None:
        for role in ROLES:
            with self.subTest(role=role):
                self.assertIn(role, ROLE_PERMISSIONS)
                self.assertLessEqual(ROLE_PERMISSIONS[role], set(PERMISSIONS))

    def test_roles_compose_by_union(self) -> None:
        merged = derive_permissions(("preparer", "reviewer"))
        self.assertTrue({"match.propose", "match.confirm"} <= merged)

    def test_a_preparer_cannot_confirm_and_a_reviewer_cannot_propose(self) -> None:
        preparer = context(roles=("preparer",))
        reviewer = context(roles=("reviewer",))
        self.assertTrue(preparer.has("match.propose"))
        self.assertFalse(preparer.has("match.confirm"))
        self.assertTrue(reviewer.has("match.confirm"))
        self.assertFalse(reviewer.has("match.propose"))

    def test_segregation_of_duties_catches_both_directions(self) -> None:
        self.assertEqual(violates_segregation("match.confirm", {"match.propose"}),
                         "match.propose")
        self.assertEqual(violates_segregation("close.approve", {"close.prepare"}),
                         "close.prepare")
        self.assertIsNone(violates_segregation("match.confirm", {"document.upload"}))

    def test_an_owner_holding_both_still_violates_segregation_per_object(self) -> None:
        # Un owner tiene ambos permisos, y aun asi no puede ejercerlos sobre el
        # mismo objeto: el rol concede, la SoD restringe por objeto.
        owner = context(roles=("owner",))
        self.assertTrue(owner.has("match.propose") and owner.has("match.confirm"))
        self.assertEqual(violates_segregation("match.confirm", {"match.propose"}),
                         "match.propose")


class ProblemTests(unittest.TestCase):
    def test_a_problem_is_rfc7807_shaped(self) -> None:
        payload = problem("invalid-request", "Invalid request", 422, "bad field").as_dict()
        self.assertEqual(payload["status"], 422)
        self.assertTrue(payload["type"].endswith("/invalid-request"))
        self.assertNotIn("instance", payload)

    def test_extras_are_flattened_and_never_shadow_the_core_fields(self) -> None:
        payload = problem("x", "X", 400, "d", field="company_id").as_dict()
        self.assertEqual(payload["field"], "company_id")
        self.assertEqual(payload["title"], "X")


if __name__ == "__main__":
    unittest.main()
