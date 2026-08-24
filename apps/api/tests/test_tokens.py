"""Contrato del token de sesion.

Un token es la unica prueba que el servidor acepta de que alguien es quien dice.
Cada prueba de aqui describe una forma concreta de mentir con uno.
"""

from __future__ import annotations

import base64
import json
import unittest

from fincilia_platform.tokens import Claims, TokenError, issue, verify

KEY = "clave-local-sintetica-de-al-menos-32-bytes"
OTHER = "otra-clave-local-sintetica-de-32-bytes-min"
ISSUER = "fincilia-local"
AUDIENCE = "fincilia-api"
NOW = 1_800_000_000
SUBJECT = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"


def token(**overrides) -> str:
    kwargs = {"key": KEY, "issuer": ISSUER, "audience": AUDIENCE,
              "issued_at": NOW, "ttl_seconds": 900}
    kwargs.update(overrides)
    return issue(overrides.pop("subject_id", SUBJECT), **kwargs)


def check(value: str, **overrides) -> Claims:
    kwargs = {"key": KEY, "issuer": ISSUER, "audience": AUDIENCE, "now": NOW}
    kwargs.update(overrides)
    return verify(value, **kwargs)


class TokenTests(unittest.TestCase):
    def test_a_fresh_token_round_trips(self) -> None:
        claims = check(token())
        self.assertEqual(SUBJECT, claims.subject_id)
        self.assertEqual(ISSUER, claims.issuer)
        self.assertEqual(NOW + 900, claims.expires_at)

    def test_two_tokens_for_the_same_subject_differ(self) -> None:
        # Sin identificador unico, dos sesiones del mismo sujeto serian el mismo
        # token y no se podria hablar de una sola de ellas.
        self.assertNotEqual(token(), token())

    def test_another_key_does_not_verify(self) -> None:
        with self.assertRaises(TokenError):
            check(token(), key=OTHER)

    def test_a_flipped_payload_byte_does_not_verify(self) -> None:
        payload, signature = token().split(".")
        mutated = ("A" if payload[0] != "A" else "B") + payload[1:]
        with self.assertRaises(TokenError):
            check(mutated + "." + signature)

    def test_rewriting_the_subject_does_not_verify(self) -> None:
        # El ataque directo: cambiar `sub` por otro sujeto y volver a codificar.
        payload, signature = token().split(".")
        body = json.loads(base64.urlsafe_b64decode(payload + "=="))
        body["sub"] = "11111111-1111-1111-1111-111111111111"
        forged = base64.urlsafe_b64encode(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).decode().rstrip("=")
        with self.assertRaises(TokenError):
            check(forged + "." + signature)

    def test_an_unsigned_token_does_not_verify(self) -> None:
        payload = token().split(".")[0]
        for candidate in (payload, payload + ".", payload + ".none", "." + payload):
            with self.subTest(candidate=candidate[:16]):
                with self.assertRaises(TokenError):
                    check(candidate)

    def test_an_expired_token_does_not_verify(self) -> None:
        with self.assertRaises(TokenError):
            check(token(), now=NOW + 901)

    def test_a_token_expiring_exactly_now_does_not_verify(self) -> None:
        # El borde se decide a favor de denegar.
        with self.assertRaises(TokenError):
            check(token(), now=NOW + 900)

    def test_a_token_from_the_future_does_not_verify(self) -> None:
        with self.assertRaises(TokenError):
            check(token(issued_at=NOW + 3600), now=NOW)

    def test_a_token_for_another_audience_does_not_verify(self) -> None:
        with self.assertRaises(TokenError):
            check(token(audience="otro-servicio"))

    def test_a_token_from_another_issuer_does_not_verify(self) -> None:
        with self.assertRaises(TokenError):
            check(token(issuer="otro-emisor"))

    def test_garbage_does_not_verify(self) -> None:
        for candidate in ("", "...", "a.b.c", "no-separator", "!!.??"):
            with self.subTest(candidate=candidate):
                with self.assertRaises(TokenError):
                    check(candidate)

    def test_a_non_string_does_not_verify(self) -> None:
        for candidate in (None, 42, b"bytes", {"sub": SUBJECT}):
            with self.subTest(candidate=type(candidate).__name__):
                with self.assertRaises(TokenError):
                    check(candidate)  # type: ignore[arg-type]

    def test_a_token_without_a_subject_is_never_issued(self) -> None:
        with self.assertRaises(TokenError):
            issue("", key=KEY, issuer=ISSUER, audience=AUDIENCE, issued_at=NOW,
                  ttl_seconds=900)

    def test_a_token_that_never_expires_is_never_issued(self) -> None:
        for ttl in (0, -1, -900):
            with self.subTest(ttl=ttl):
                with self.assertRaises(TokenError):
                    issue(SUBJECT, key=KEY, issuer=ISSUER, audience=AUDIENCE,
                          issued_at=NOW, ttl_seconds=ttl)

    def test_the_token_carries_no_permissions(self) -> None:
        # Si llevara roles, revocarlos no surtiria efecto hasta que caducase.
        body = json.loads(base64.urlsafe_b64decode(token().split(".")[0] + "=="))
        for forbidden in ("roles", "permissions", "company", "company_id", "scope"):
            self.assertNotIn(forbidden, body)

    def test_the_algorithm_does_not_travel_in_the_token(self) -> None:
        # Sin `alg` en el token no hay confusion de algoritmo ni `alg: none`.
        body = json.loads(base64.urlsafe_b64decode(token().split(".")[0] + "=="))
        self.assertNotIn("alg", body)


if __name__ == "__main__":
    unittest.main()
