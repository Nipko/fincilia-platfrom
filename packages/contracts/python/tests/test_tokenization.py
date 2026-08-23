"""Tokenizacion de identificadores de cuenta.

Lo que se comprueba aqui es que el numero no sobreviva a la funcion: ni en el
token, ni en la cola visible, ni en el mensaje de un error.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fincilia_contracts.tokenization import (  # noqa: E402
    MIN_KEY_LENGTH,
    TOKEN_LENGTH,
    TokenizationError,
    matches,
    normalise,
    redact,
    tokenize,
)

KEY = "clave_sintetica_de_pruebas_de_32_caracteres"
OTHER_KEY = "otra_clave_sintetica_distinta_de_32_caracteres"
COMPANY = "11111111-1111-5111-8111-111111111111"
OTHER_COMPANY = "22222222-2222-5222-8222-222222222222"


class TokenTests(unittest.TestCase):
    def test_the_same_account_always_produces_the_same_token(self) -> None:
        # Es lo que permite detectar un alta duplicada sin guardar el numero.
        first = tokenize("1234567890", key=KEY, company_id=COMPANY)
        second = tokenize("1234567890", key=KEY, company_id=COMPANY)
        self.assertEqual(first.token, second.token)
        self.assertEqual(len(first.token), TOKEN_LENGTH)

    def test_separators_and_case_do_not_change_the_account(self) -> None:
        # `1234-5678` y `1234 5678` son la misma cuenta. Si dieran tokens
        # distintos, el alta duplicada pasaria desapercibida.
        canonical = tokenize("CO12345678", key=KEY, company_id=COMPANY).token
        for written in ("co-1234-5678", "CO 1234 5678", "co.1234.5678", " CO12345678 "):
            with self.subTest(written=written):
                self.assertEqual(
                    tokenize(written, key=KEY, company_id=COMPANY).token, canonical)

    def test_the_token_never_contains_the_identifier(self) -> None:
        result = tokenize("4111111111111111", key=KEY, company_id=COMPANY)
        self.assertNotIn("4111", result.token[:-4] + "0000")
        self.assertRegex(result.token, r"^[0-9a-f]{64}$")

    def test_the_same_number_in_two_companies_gives_two_tokens(self) -> None:
        # Sin esto, comparar tokens entre empresas revelaria que comparten una
        # cuenta, que es una relacion que nadie ha autorizado a conocer.
        here = tokenize("1234567890", key=KEY, company_id=COMPANY)
        there = tokenize("1234567890", key=KEY, company_id=OTHER_COMPANY)
        self.assertNotEqual(here.token, there.token)

    def test_another_key_gives_another_token(self) -> None:
        self.assertNotEqual(
            tokenize("1234567890", key=KEY, company_id=COMPANY).token,
            tokenize("1234567890", key=OTHER_KEY, company_id=COMPANY).token)

    def test_rotating_the_key_version_changes_the_token_and_is_recorded(self) -> None:
        # La identidad economica de la cuenta no cambia al rotar: cambia el token,
        # y por eso la version viaja al lado y no dentro.
        first = tokenize("1234567890", key=KEY, key_version=1, company_id=COMPANY)
        second = tokenize("1234567890", key=KEY, key_version=2, company_id=COMPANY)
        self.assertNotEqual(first.token, second.token)
        self.assertEqual(first.key_version, 1)
        self.assertEqual(second.key_version, 2)


class Last4Tests(unittest.TestCase):
    def test_a_bank_account_keeps_four_digits_a_person_can_recognise(self) -> None:
        result = tokenize("CO-1234-567890", key=KEY, company_id=COMPANY,
                          account_family="bank_account")
        self.assertEqual(result.last4, "7890")

    def test_a_ledger_has_no_visible_tail_because_it_would_mean_nothing(self) -> None:
        result = tokenize("LIBRO-000123", key=KEY, company_id=COMPANY,
                          account_family="accounting_ledger")
        self.assertIsNone(result.last4)

    def test_an_identifier_with_too_few_digits_has_no_tail(self) -> None:
        result = tokenize("ABC-12", key=KEY, company_id=COMPANY,
                          account_family="bank_account")
        self.assertIsNone(result.last4)


class RefusalTests(unittest.TestCase):
    def test_a_short_key_is_refused(self) -> None:
        with self.assertRaises(TokenizationError) as caught:
            tokenize("1234567890", key="corta", company_id=COMPANY)
        self.assertIn(str(MIN_KEY_LENGTH), str(caught.exception))

    def test_an_empty_identifier_is_refused(self) -> None:
        for value in ("", "   ", "---", "..."):
            with self.subTest(value=value):
                with self.assertRaises(TokenizationError):
                    tokenize(value, key=KEY, company_id=COMPANY)

    def test_a_refusal_never_quotes_the_identifier(self) -> None:
        # Un mensaje de error acaba en un log. Si llevara el numero, la
        # tokenizacion no serviria de nada.
        secret = "4111111111111111!!!"
        with self.assertRaises(TokenizationError) as caught:
            tokenize(secret, key=KEY, company_id=COMPANY)
        self.assertNotIn("4111", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))

    def test_a_key_version_out_of_range_is_refused(self) -> None:
        for version in (0, -1, 1000):
            with self.subTest(version=version):
                with self.assertRaises(TokenizationError):
                    tokenize("1234567890", key=KEY, key_version=version,
                             company_id=COMPANY)

    def test_a_non_text_identifier_is_refused(self) -> None:
        with self.assertRaises(TokenizationError):
            normalise(1234567890)  # type: ignore[arg-type]


class ComparisonTests(unittest.TestCase):
    def test_a_matching_candidate_is_recognised(self) -> None:
        stored = tokenize("CO12345678", key=KEY, company_id=COMPANY).token
        self.assertTrue(matches("co-1234-5678", stored, key=KEY, key_version=1,
                                account_family="bank_account", company_id=COMPANY))

    def test_a_different_account_is_not_recognised(self) -> None:
        stored = tokenize("CO12345678", key=KEY, company_id=COMPANY).token
        self.assertFalse(matches("CO12345679", stored, key=KEY, key_version=1,
                                 account_family="bank_account", company_id=COMPANY))

    def test_an_unusable_candidate_is_a_no_match_and_not_a_crash(self) -> None:
        stored = tokenize("CO12345678", key=KEY, company_id=COMPANY).token
        self.assertFalse(matches("", stored, key=KEY, key_version=1,
                                 account_family="bank_account", company_id=COMPANY))


class RedactionTests(unittest.TestCase):
    def test_redaction_shows_the_tail_and_nothing_else(self) -> None:
        self.assertEqual(redact("CO-1234-567890"), "...7890")

    def test_redaction_of_something_without_digits_says_so(self) -> None:
        self.assertEqual(redact("SIN-DIGITOS"), "(sin cola visible)")
        self.assertEqual(redact(""), "(sin cola visible)")


if __name__ == "__main__":
    unittest.main()
