from __future__ import annotations

import copy
import hashlib
import json
import unittest

from .probe import DOMAIN, HEADER_NAMES, PUBLIC_PATHS, _canonical_digest, _source_digest, validate_evidence


def _headers() -> dict[str, str]:
    values = {
        "cache-control": "private, no-cache, no-store, max-age=0, must-revalidate",
        "content-security-policy": (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'; base-uri 'none'"
        ),
        "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=()",
        "referrer-policy": "strict-origin-when-cross-origin",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
    }
    assert tuple(sorted(values)) == tuple(sorted(HEADER_NAMES))
    return values


def _evidence() -> dict:
    routes = []
    for path in PUBLIC_PATHS:
        headers = _headers()
        routes.append({
            "path": path,
            "status": 200,
            "headers": headers,
            "headers_sha256": hashlib.sha256(json.dumps(
                headers, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest(),
        })
    checks = {
        "certificate_covers_domain": True,
        "certificate_trusted": True,
        "csp_blocks_framing": True,
        "csp_forbids_unsafe_eval": True,
        "http_redirect_exact": True,
        "https_routes_ok": True,
        "hsts_exact": True,
        "no_store_exact": True,
        "nosniff_exact": True,
        "permissions_policy_exact": True,
        "referrer_policy_exact": True,
        "tls_modern": True,
        "x_frame_options_exact": True,
    }
    payload = {
        "schema_version": "1.0.0",
        "task_id": "FNC-UAT-003",
        "status": "passed",
        "domain": DOMAIN,
        "environment": "uat",
        "data_classification": "completely_synthetic",
        "observed_at": "2026-09-02T23:57:24Z",
        "source_revision": "a" * 40,
        "request_policy": {
            "methods": ["HEAD"],
            "authorization_sent": False,
            "body_sent_or_captured": False,
            "cookies_sent": False,
            "query_strings_sent": False,
        },
        "transport": {
            "http_status": 301,
            "http_location": f"https://{DOMAIN}/",
            "tls_verified": True,
            "tls_version": "TLSv1.3",
            "cipher": "TLS_AES_256_GCM_SHA384",
            "certificate_sha256": "b" * 64,
            "certificate_san": [DOMAIN],
            "certificate_issuer_common_name": "Synthetic CA",
            "certificate_not_after": "2026-11-30T00:00:00Z",
        },
        "routes": routes,
        "checks": checks,
        "probe_source_sha256": _source_digest(),
        "independent_review": {
            "state": "pending",
            "required_roles": ["Security", "Platform/SRE", "QA"],
            "agent_observation_is_not_acceptance": True,
        },
        "real_data_authorized": False,
        "production_authorized": False,
    }
    payload["evidence_sha256"] = _canonical_digest(payload)
    return payload


def _resign(payload: dict) -> None:
    for route in payload.get("routes", []):
        headers = route.get("headers")
        if isinstance(headers, dict):
            route["headers_sha256"] = hashlib.sha256(json.dumps(
                headers, sort_keys=True, separators=(",", ":")
            ).encode()).hexdigest()
    payload["evidence_sha256"] = _canonical_digest(payload)


class UatEdgeProbeTests(unittest.TestCase):
    def test_valid_evidence_passes_offline(self) -> None:
        self.assertEqual([], validate_evidence(_evidence()))

    def test_critical_mutations_bite(self) -> None:
        mutations = (
            ("EDGE-CLAIM", lambda item: item.update({"domain": "example.invalid"})),
            ("EDGE-PRIVACY", lambda item: item["request_policy"].update({"cookies_sent": True})),
            ("EDGE-TRANSPORT", lambda item: item["transport"].update({"tls_verified": False})),
            ("EDGE-ROUTES", lambda item: item["routes"].pop()),
            ("EDGE-HEADERS", lambda item: item["routes"][0]["headers"].update(
                {"strict-transport-security": ""})),
            ("EDGE-HEADERS", lambda item: item["routes"][0]["headers"].update(
                {"content-security-policy": "script-src 'unsafe-eval'"})),
            ("EDGE-CHECKS", lambda item: item["checks"].update({"tls_modern": False})),
            ("EDGE-REVIEW", lambda item: item["independent_review"].update(
                {"state": "accepted"})),
            ("EDGE-SOURCE", lambda item: item.update({"probe_source_sha256": "0" * 64})),
        )
        for expected, mutation in mutations:
            with self.subTest(expected=expected):
                candidate = copy.deepcopy(_evidence())
                mutation(candidate)
                _resign(candidate)
                self.assertIn(expected, validate_evidence(candidate))

    def test_evidence_digest_mutation_bites(self) -> None:
        candidate = _evidence()
        candidate["evidence_sha256"] = "0" * 64
        self.assertIn("EDGE-EVIDENCE-DIGEST", validate_evidence(candidate))

    def test_revision_must_be_full_sha(self) -> None:
        candidate = _evidence()
        candidate["source_revision"] = "abc1234"
        _resign(candidate)
        self.assertIn("EDGE-REVISION", validate_evidence(candidate))
