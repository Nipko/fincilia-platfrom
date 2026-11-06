"""Pruebas puras del contrato de perfil operativo (ADR-039, FNC-SMB-001).

Las guardas autoritativas viven en PostgreSQL y se prueban en
``db/tests/test_operating_profile.py``. Aqui se fija lo que la API decide antes
de llegar a la base, sin conexion real.
"""

from __future__ import annotations

import datetime as dt
import unittest

from fincilia_api import company_onboarding, operating_profile
from fincilia_api.close_period import _row


class _NoDatabase:
    """Falla si alguien intenta tocar la base: la negativa debe ocurrir antes."""

    def cursor(self):  # pragma: no cover - solo se ejecuta si hay regresion
        raise AssertionError("the database must not be reached")

    def transaction(self):  # pragma: no cover
        raise AssertionError("the database must not be reached")


class _ProfileCursor:
    def __init__(self, profile):
        self.profile = profile

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_args, **_kwargs):
        return None

    def fetchone(self):
        return None if self.profile is None else (self.profile,)


class _ProfileConnection:
    def __init__(self, profile):
        self.profile = profile

    def cursor(self):
        return _ProfileCursor(self.profile)


COMPANY = "11111111-1111-4111-8111-111111111111"
ALICE = "21111111-1111-4111-8111-111111111111"
BRUNO = "31111111-1111-4111-8111-111111111111"


class InitialProfileTests(unittest.TestCase):
    def test_without_answer_the_safe_default_is_strict(self) -> None:
        self.assertEqual("estricto", operating_profile.resolve_initial_profile(
            operating_profile=None, team_size_band=None))

    def test_team_size_band_suggests_and_explicit_choice_wins(self) -> None:
        self.assertEqual("simple", operating_profile.resolve_initial_profile(
            operating_profile=None, team_size_band="1-2"))
        self.assertEqual("estricto", operating_profile.resolve_initial_profile(
            operating_profile=None, team_size_band="3+"))
        self.assertEqual("estricto", operating_profile.resolve_initial_profile(
            operating_profile="estricto", team_size_band="1-2"))
        self.assertEqual("simple", operating_profile.resolve_initial_profile(
            operating_profile="simple", team_size_band="3+"))

    def test_unknown_values_are_rejected(self) -> None:
        with self.assertRaises(operating_profile.OperatingProfileError):
            operating_profile.resolve_initial_profile(
                operating_profile="laxo", team_size_band=None)
        with self.assertRaises(operating_profile.OperatingProfileError):
            operating_profile.resolve_initial_profile(
                operating_profile=None, team_size_band="10")


class ProvisioningDigestTests(unittest.TestCase):
    BASE = {"firm_id": COMPANY, "legal_name": "Empresa Sintetica",
            "country_code": "CO", "tax_token": "tok", "setup": None,
            "account_request_token": None}

    def test_strict_keeps_the_pre_adr_digest(self) -> None:
        legacy = company_onboarding._request_digest(**self.BASE)
        strict = company_onboarding._request_digest(
            **self.BASE, operating_profile="estricto")
        self.assertEqual(legacy, strict)

    def test_simple_changes_the_digest(self) -> None:
        legacy = company_onboarding._request_digest(**self.BASE)
        simple = company_onboarding._request_digest(
            **self.BASE, operating_profile="simple")
        self.assertNotEqual(legacy, simple)


class ReviewModeTests(unittest.TestCase):
    def test_different_actors_are_always_independent(self) -> None:
        for profile in ("simple", "estricto", None):
            with self.subTest(profile=profile):
                self.assertEqual("independent", operating_profile.review_mode_for(
                    _ProfileConnection(profile), company_id=COMPANY,
                    proposer_id=ALICE, decider_id=BRUNO))

    def test_same_actor_is_self_reviewed_only_in_simple(self) -> None:
        self.assertEqual("self_reviewed", operating_profile.review_mode_for(
            _ProfileConnection("simple"), company_id=COMPANY,
            proposer_id=ALICE, decider_id=ALICE))
        self.assertIsNone(operating_profile.review_mode_for(
            _ProfileConnection("estricto"), company_id=COMPANY,
            proposer_id=ALICE, decider_id=ALICE))

    def test_invisible_or_unknown_profile_is_strict(self) -> None:
        self.assertEqual("estricto", operating_profile.current_profile(
            _ProfileConnection(None), COMPANY))
        self.assertEqual("estricto", operating_profile.current_profile(
            _ProfileConnection("otro"), COMPANY))
        self.assertFalse(operating_profile.allows_self_review(
            _ProfileConnection(None), COMPANY))


class ChangeProfileTests(unittest.TestCase):
    def test_non_owner_is_refused_before_the_database(self) -> None:
        with self.assertRaises(operating_profile.OperatingProfileError) as raised:
            operating_profile.change_profile(
                _NoDatabase(), company_id=COMPANY, actor_id=ALICE,
                roles=("reviewer", "preparer"), operating_profile="simple",
                reason="Motivo sintetico suficiente")
        self.assertEqual("operating-profile-owner-required", raised.exception.code)
        self.assertEqual(403, raised.exception.status)

    def test_reason_and_profile_are_validated(self) -> None:
        for profile, reason in (("simple", "corto"), ("simple", "x" * 501),
                                ("simple", "Motivo\x00con control"),
                                ("relajado", "Motivo sintetico suficiente")):
            with self.subTest(profile=profile, reason=reason[:10]):
                with self.assertRaises(operating_profile.OperatingProfileError):
                    operating_profile.change_profile(
                        _NoDatabase(), company_id=COMPANY, actor_id=ALICE,
                        roles=("owner",), operating_profile=profile, reason=reason)


class CloseCertificationRowTests(unittest.TestCase):
    BASE = (
        "71111111-1111-4111-8111-111111111111", dt.date(2026, 7, 1),
        dt.date(2026, 7, 31), 1, "81111111-1111-4111-8111-111111111111", "a" * 64,
        "accounting-close-v1", {}, "b" * 64, ALICE, "Owner",
        dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc),
        None, None, None, None, None, None, None, None, None, None, None, None,
    )

    def test_legacy_row_is_independent_and_certified(self) -> None:
        result = _row(self.BASE)
        self.assertEqual("independent", result["review_mode"])
        self.assertEqual("certified", result["certification"])
        self.assertIsNone(result["certification_record"])

    def test_self_reviewed_close_waits_for_certification(self) -> None:
        pending = _row(self.BASE + ("self_reviewed", "self_reviewed",
                                    None, None, None, None, None))
        self.assertEqual("self_reviewed", pending["certification"])
        self.assertIsNone(pending["certification_record"])
        certified = _row(self.BASE + (
            "self_reviewed", "self_reviewed", "91111111-1111-4111-8111-111111111111",
            BRUNO, "Contador", dt.datetime(2026, 8, 5, tzinfo=dt.timezone.utc), None))
        self.assertEqual("certified", certified["certification"])
        self.assertEqual("self_reviewed", certified["review_mode"])
        self.assertEqual(BRUNO, certified["certification_record"]["certified_by"])


if __name__ == "__main__":
    unittest.main()
