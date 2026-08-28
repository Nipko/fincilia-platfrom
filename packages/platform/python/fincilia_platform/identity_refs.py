"""Referencias irreversibles para identificadores personales de identidad."""

from __future__ import annotations

import hashlib
import hmac
import re


EMAIL = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,189}$")


class IdentityReferenceError(ValueError):
    pass


def canonical_email(value: str) -> str:
    canonical = value.strip().casefold()
    if len(canonical) > 254 or not EMAIL.fullmatch(canonical):
        raise IdentityReferenceError("email identity is invalid")
    return canonical


def hmac_reference(key: str, *, purpose: str, value: str) -> str:
    if len(key) < 32 or not re.fullmatch(r"[a-z0-9-]{3,40}", purpose):
        raise IdentityReferenceError("identity reference configuration is invalid")
    digest = hmac.new(
        key.encode("utf-8"),
        f"fincilia:{purpose}:v1\x00{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"hmac-sha256:v1:{digest}"


def email_reference(key: str, email: str) -> str:
    return hmac_reference(
        key, purpose="verified-email", value=canonical_email(email))
