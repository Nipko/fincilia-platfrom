"""Contrato del proveedor de identidad local y del hash de credenciales."""

from __future__ import annotations

import unittest

from fincilia_platform.identity import (ALGORITHM, ITERATIONS, AuthenticationError,
                                        Credential, LocalIdentityProvider,
                                        hash_secret, new_salt, verify_secret)

SUBJECT = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
SECRET = "fincilia-demo-only"


def credential(secret: str = SECRET, **overrides) -> Credential:
    salt = overrides.pop("salt", new_salt())
    fields = {"subject_id": SUBJECT, "username": "ana@demo.local",
              "algorithm": ALGORITHM, "iterations": ITERATIONS, "salt": salt,
              "secret_hash": hash_secret(secret, salt=salt)}
    fields.update(overrides)
    return Credential(**fields)


class HashTests(unittest.TestCase):
    def test_the_same_secret_and_salt_derive_the_same_hash(self) -> None:
        salt = new_salt()
        self.assertEqual(hash_secret(SECRET, salt=salt), hash_secret(SECRET, salt=salt))

    def test_the_same_secret_with_another_salt_derives_another_hash(self) -> None:
        # Sin sal por usuario, dos personas con la misma contrasena comparten hash
        # y una tabla precalculada las abre a las dos.
        self.assertNotEqual(hash_secret(SECRET, salt=new_salt()),
                            hash_secret(SECRET, salt=new_salt()))

    def test_an_empty_secret_is_not_a_credential(self) -> None:
        with self.assertRaises(ValueError):
            hash_secret("", salt=new_salt())

    def test_the_iteration_floor_is_enforced(self) -> None:
        with self.assertRaises(ValueError):
            hash_secret(SECRET, salt=new_salt(), iterations=1)

    def test_the_default_cost_matches_the_schema_floor(self) -> None:
        # El CHECK de `local_credential` exige >= 200000. Si el codigo bajara por
        # debajo, la insercion fallaria en tiempo de siembra y no antes.
        self.assertGreaterEqual(ITERATIONS, 200_000)

    def test_a_salt_is_the_shape_the_schema_accepts(self) -> None:
        self.assertRegex(new_salt(), r"^[0-9a-f]{32}$")

    def test_verification_accepts_the_right_secret(self) -> None:
        self.assertTrue(verify_secret(SECRET, credential()))

    def test_verification_rejects_the_wrong_secret(self) -> None:
        for wrong in ("", "otra", SECRET + " ", SECRET.upper()):
            with self.subTest(wrong=wrong):
                self.assertFalse(verify_secret(wrong, credential()))

    def test_an_unknown_algorithm_never_verifies(self) -> None:
        # Falla cerrado: no se intenta adivinar como se derivo el hash.
        self.assertFalse(verify_secret(SECRET, credential(algorithm="md5")))


class LocalProviderTests(unittest.TestCase):
    def provider(self, record: Credential | None, **kwargs) -> LocalIdentityProvider:
        return LocalIdentityProvider(lambda username: record, **kwargs)

    def test_the_right_secret_identifies_the_subject(self) -> None:
        identity = self.provider(credential()).authenticate("ana@demo.local", SECRET)
        self.assertEqual(SUBJECT, identity.subject_id)
        self.assertEqual("local", identity.issuer)

    def test_the_wrong_secret_is_rejected(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.provider(credential()).authenticate("ana@demo.local", "otra")

    def test_an_unknown_user_is_rejected_the_same_way(self) -> None:
        # Mismo tipo de error y mismo mensaje que una contrasena incorrecta: la
        # respuesta no puede decir que cuentas existen.
        unknown = self.assertRaises(AuthenticationError)
        with unknown:
            self.provider(None).authenticate("nadie@demo.local", SECRET)
        known = self.assertRaises(AuthenticationError)
        with known:
            self.provider(credential()).authenticate("ana@demo.local", "otra")
        self.assertEqual(str(unknown.exception), str(known.exception))

    def test_an_empty_username_is_rejected(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.provider(credential()).authenticate("", SECRET)

    def test_an_empty_secret_is_rejected(self) -> None:
        with self.assertRaises(AuthenticationError):
            self.provider(credential()).authenticate("ana@demo.local", "")

    def test_it_refuses_to_exist_alongside_real_data(self) -> None:
        # En el constructor, no en una nota: un almacen de contrasenas sinteticas
        # junto a datos reales no debe llegar a instanciarse.
        with self.assertRaises(RuntimeError):
            self.provider(credential(), real_data_enabled=True)


if __name__ == "__main__":
    unittest.main()
