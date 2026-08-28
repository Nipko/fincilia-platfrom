"""Contrato puro del registro sintetico; PostgreSQL tiene su suite propia."""

from __future__ import annotations

import unittest

from fincilia_api.registration import (
    RegistrationError,
    clean_name,
    invitation_digest,
    normalise_username,
    register_local_account,
    validate_secret,
)


class RegistrationValidationTests(unittest.TestCase):
    def test_username_is_normalised_and_synthetic_only(self) -> None:
        self.assertEqual(
            "alex.registro@demo.local",
            normalise_username("  Alex.Registro@DEMO.LOCAL "),
        )
        for value in (
            "alex@example.com", "alex@demo.local.example", "@demo.local",
            "a@demo.local", "alex registro@demo.local",
        ):
            with self.subTest(value=value), self.assertRaises(RegistrationError):
                normalise_username(value)

    def test_password_policy_requires_length_and_four_classes(self) -> None:
        validate_secret("Registro-Demo-2026!")
        for value in (
            "Corta-1!", "registro-demo-2026!", "REGISTRO-DEMO-2026!",
            "Registro-Demo-SinNumero!", "RegistroDemo2026SinSimbolo",
        ):
            with self.subTest(value=value), self.assertRaises(RegistrationError):
                validate_secret(value)

    def test_invitation_is_bounded_and_only_its_digest_survives(self) -> None:
        code = "Beta_Cerrada_2026_codigo_A1"
        digest = invitation_digest(code)
        self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn(code, digest)
        for value in (None, "corto", "codigo con espacios que no se admite"):
            with self.subTest(value=value), self.assertRaises(RegistrationError):
                invitation_digest(value)

    def test_profile_names_are_trimmed_bounded_and_control_free(self) -> None:
        self.assertEqual("Alex Demo", clean_name(
            "  Alex   Demo  ", kind="display name", maximum=200))
        for value in ("x", "Alex\x00Demo", "A" * 201):
            with self.subTest(value=value), self.assertRaises(RegistrationError):
                clean_name(value, kind="display name", maximum=200)

    def test_real_data_stops_before_touching_the_database(self) -> None:
        with self.assertRaises(RegistrationError) as raised:
            register_local_account(
                object(),  # type: ignore[arg-type]
                username="alex@demo.local",
                secret="Registro-Demo-2026!",
                display_name="Alex Demo",
                firm_name="Firma Demo",
                real_data_enabled=True,
            )
        self.assertEqual(503, raised.exception.status)


if __name__ == "__main__":
    unittest.main()
