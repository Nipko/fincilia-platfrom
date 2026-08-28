"""Verificación criptográfica de gates de datos en runtime.

Una variable de entorno puede seleccionar un entorno; no puede autorizar datos.
La autorización es un documento canónico firmado por una clave KMS asimétrica.
Los roles de aplicación reciben ``kms:Verify`` y nunca ``kms:Sign``.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


SHA256 = re.compile(r"^[0-9a-f]{64}$")
GATES = {"DRG-00", "DRG-01"}
KMS_KEY_ARN = re.compile(
    r"^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[0-9a-fA-F-]{36}$")


class GateVerificationError(RuntimeError):
    """El proceso no tiene una autorización de datos auténtica y vigente."""


@dataclass(frozen=True)
class GateAttestation:
    gate: str
    pilot_id: str
    expires_at: dt.datetime
    evidence_digest: str
    approver_ids: tuple[str, ...]


def canonical_payload(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")


def parse_attestation(raw: str, *, required_gate: str,
                      now: dt.datetime | None = None) -> tuple[GateAttestation, bytes]:
    if required_gate not in GATES:
        raise GateVerificationError("unsupported data gate")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 16_384:
        raise GateVerificationError("data gate attestation exceeds its size limit")
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as error:
        raise GateVerificationError("data gate attestation is not valid JSON") from error
    expected = {
        "schema_version", "gate", "environment", "status", "authorized",
        "pilot_id", "issued_at", "expires_at", "evidence_digest",
        "approver_ids",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise GateVerificationError("data gate attestation fields drifted")
    if (
        value.get("schema_version") != "1.0.0"
        or value.get("gate") != required_gate
        or value.get("environment") != "private-pilot"
        or value.get("status") != "met"
        or value.get("authorized") is not True
    ):
        raise GateVerificationError("data gate attestation does not authorize this runtime")
    pilot_id = value.get("pilot_id")
    if not isinstance(pilot_id, str) or not re.fullmatch(r"fnc-pilot-[a-z0-9-]{3,48}", pilot_id):
        raise GateVerificationError("pilot identifier is invalid")
    digest = value.get("evidence_digest")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise GateVerificationError("evidence digest is invalid")
    approvers = value.get("approver_ids")
    if (
        not isinstance(approvers, list) or len(approvers) < 2
        or len(approvers) != len(set(approvers))
        or any(not isinstance(item, str) or not re.fullmatch(r"[A-Z0-9-]{3,64}", item)
               for item in approvers)
        or set(approvers) == {"FOUNDER-01"}
    ):
        raise GateVerificationError("independent approver evidence is missing")
    try:
        issued_at = dt.datetime.fromisoformat(str(value["issued_at"]).replace("Z", "+00:00"))
        expires_at = dt.datetime.fromisoformat(str(value["expires_at"]).replace("Z", "+00:00"))
    except ValueError as error:
        raise GateVerificationError("attestation timestamps are invalid") from error
    if issued_at.tzinfo is None or expires_at.tzinfo is None:
        raise GateVerificationError("attestation timestamps need time zones")
    current = now or dt.datetime.now(dt.UTC)
    if issued_at >= expires_at:
        raise GateVerificationError("attestation validity interval is empty")
    if issued_at > current + dt.timedelta(minutes=5) or expires_at <= current:
        raise GateVerificationError("data gate attestation is not currently valid")
    if expires_at - issued_at > dt.timedelta(days=90):
        raise GateVerificationError("data gate attestation exceeds the 90 day ceiling")
    return (
        GateAttestation(required_gate, pilot_id, expires_at, digest, tuple(approvers)),
        canonical_payload(value),
    )


def verify_kms_attestation(*, raw: str, signature_b64: str, key_id: str,
                           required_gate: str, kms_client=None,
                           now: dt.datetime | None = None) -> GateAttestation:
    attestation, message = parse_attestation(raw, required_gate=required_gate, now=now)
    if not isinstance(signature_b64, str) or len(signature_b64) > 4096:
        raise GateVerificationError("data gate signature exceeds its size limit")
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except (ValueError, TypeError) as error:
        raise GateVerificationError("data gate signature is not base64") from error
    if not signature or not KMS_KEY_ARN.fullmatch(key_id):
        raise GateVerificationError("data gate signature or KMS key is missing")
    client = kms_client or boto3.client("kms")
    try:
        response = client.verify(
            KeyId=key_id,
            Message=message,
            MessageType="RAW",
            Signature=signature,
            SigningAlgorithm="RSASSA_PSS_SHA_256",
        )
    except (BotoCoreError, ClientError) as error:
        raise GateVerificationError("KMS could not verify the data gate") from error
    if response.get("SignatureValid") is not True:
        raise GateVerificationError("data gate signature is invalid")
    return attestation


def verify_configured_gate(settings, *, required_gate: str, kms_client=None,
                           now: dt.datetime | None = None) -> GateAttestation:
    if required_gate == "DRG-00":
        raw = settings.identity_gate_attestation
        signature = settings.identity_gate_signature
        key_id = settings.identity_gate_kms_key_id
    elif required_gate == "DRG-01":
        raw = settings.data_gate_attestation
        signature = settings.data_gate_signature
        key_id = settings.data_gate_kms_key_id
    else:
        raise GateVerificationError("unsupported data gate")
    return verify_kms_attestation(
        raw=raw,
        signature_b64=signature,
        key_id=key_id,
        required_gate=required_gate,
        kms_client=kms_client,
        now=now,
    )
