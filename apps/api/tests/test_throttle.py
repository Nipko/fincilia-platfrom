"""Contrato del freno de intentos.

Lo que se prueba no es que cuente bien, sino que **falle abierto**: una cache
caida encarece la fuerza bruta menos, pero no deja a nadie sin poder entrar.
"""

from __future__ import annotations

import unittest

from fincilia_api.throttle import MAX_ATTEMPTS, AttemptThrottle, attempt_key


class FakeClient:
    def __init__(self, *, broken: bool = False) -> None:
        self.store: dict[str, int] = {}
        self.expiries: dict[str, int] = {}
        self.broken = broken

    def _guard(self) -> None:
        if self.broken:
            raise ConnectionError("cache unavailable")

    def get(self, key: str):
        self._guard()
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self._guard()
        self.store.pop(key, None)

    def pipeline(self) -> "FakePipeline":
        self._guard()
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.queue: list = []

    def incr(self, key: str) -> None:
        self.queue.append(("incr", key))

    def expire(self, key: str, seconds: int) -> None:
        self.queue.append(("expire", key, seconds))

    def execute(self) -> None:
        self.client._guard()
        for command in self.queue:
            if command[0] == "incr":
                self.client.store[command[1]] = self.client.store.get(command[1], 0) + 1
            else:
                self.client.expiries[command[1]] = command[2]


class ThrottleTests(unittest.TestCase):
    def test_a_quiet_user_is_never_throttled(self) -> None:
        self.assertFalse(AttemptThrottle(FakeClient()).exhausted("ana@demo.local"))

    def test_the_limit_bites_only_after_it_is_reached(self) -> None:
        throttle = AttemptThrottle(FakeClient())
        for _ in range(MAX_ATTEMPTS - 1):
            throttle.record_failure("ana@demo.local")
        self.assertFalse(throttle.exhausted("ana@demo.local"))
        throttle.record_failure("ana@demo.local")
        self.assertTrue(throttle.exhausted("ana@demo.local"))

    def test_a_successful_sign_in_clears_the_count(self) -> None:
        throttle = AttemptThrottle(FakeClient())
        for _ in range(MAX_ATTEMPTS):
            throttle.record_failure("ana@demo.local")
        throttle.clear("ana@demo.local")
        self.assertFalse(throttle.exhausted("ana@demo.local"))

    def test_failures_are_counted_per_user(self) -> None:
        throttle = AttemptThrottle(FakeClient())
        for _ in range(MAX_ATTEMPTS):
            throttle.record_failure("ana@demo.local")
        self.assertFalse(throttle.exhausted("beto@demo.local"))

    def test_the_window_is_bounded(self) -> None:
        client = FakeClient()
        AttemptThrottle(client).record_failure("ana@demo.local")
        # Sin caducidad, un usuario bloqueado por una racha vieja no se recupera.
        self.assertIn(attempt_key("ana@demo.local"), client.expiries)
        self.assertGreater(client.expiries[attempt_key("ana@demo.local")], 0)

    def test_the_key_does_not_carry_the_username(self) -> None:
        self.assertNotIn("ana@demo.local", attempt_key("ana@demo.local"))

    def test_a_broken_cache_fails_open(self) -> None:
        throttle = AttemptThrottle(FakeClient(broken=True))
        throttle.record_failure("ana@demo.local")
        throttle.clear("ana@demo.local")
        self.assertFalse(throttle.exhausted("ana@demo.local"))

    def test_no_cache_at_all_fails_open(self) -> None:
        throttle = AttemptThrottle(None)
        throttle.record_failure("ana@demo.local")
        self.assertFalse(throttle.exhausted("ana@demo.local"))


if __name__ == "__main__":
    unittest.main()
