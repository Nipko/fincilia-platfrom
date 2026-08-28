from __future__ import annotations

import unittest

from .invitations import code_digest, new_code


class InvitationAdminTests(unittest.TestCase):
    def test_codes_are_high_entropy_urlsafe_and_never_the_digest(self) -> None:
        first = new_code()
        second = new_code()
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^[A-Za-z0-9_-]{32}$")
        self.assertRegex(code_digest(first), r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn(first, code_digest(first))


if __name__ == "__main__":
    unittest.main()
