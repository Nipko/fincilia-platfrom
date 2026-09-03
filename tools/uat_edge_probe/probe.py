from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import re
import socket
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_PATH = ROOT / "docs/implementation/evidence/FNC-UAT-003.json"
DOMAIN = "fincilia.com"
PUBLIC_PATHS = (
    "/",
    "/entrar",
    "/registro",
    "/privacidad",
    "/terminos",
    "/cookies",
    "/seguridad",
    "/subencargados",
    "/dpa",
    "/eliminar-cuenta",
)
HEADER_NAMES = (
    "cache-control",
    "content-security-policy",
    "permissions-policy",
    "referrer-policy",
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
)
EXPECTED_CHECKS = {
    "certificate_covers_domain",
    "certificate_trusted",
    "csp_blocks_framing",
    "csp_forbids_unsafe_eval",
    "http_redirect_exact",
    "https_routes_ok",
    "hsts_exact",
    "no_store_exact",
    "nosniff_exact",
    "permissions_policy_exact",
    "referrer_policy_exact",
    "tls_modern",
    "x_frame_options_exact",
}


class EdgeProbeError(RuntimeError):
    pass


def _canonical_digest(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "evidence_sha256"}
    return hashlib.sha256(json.dumps(
        unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _source_digest() -> str:
    content = Path(__file__).read_text(encoding="utf-8")
    canonical = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _certificate() -> dict[str, Any]:
    context = ssl.create_default_context()
    with socket.create_connection((DOMAIN, 443), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname=DOMAIN) as secured:
            certificate = secured.getpeercert()
            binary = secured.getpeercert(binary_form=True)
            issuer = next((
                value
                for attributes in certificate.get("issuer", ())
                for key, value in attributes
                if key == "commonName"
            ), "")
            sans = sorted(
                value for key, value in certificate.get("subjectAltName", ())
                if key == "DNS"
            )
            not_after = datetime.fromtimestamp(
                ssl.cert_time_to_seconds(certificate["notAfter"]), timezone.utc
            )
            cipher = secured.cipher()
            return {
                "tls_verified": True,
                "tls_version": secured.version(),
                "cipher": cipher[0] if cipher else "",
                "certificate_sha256": hashlib.sha256(binary).hexdigest(),
                "certificate_san": sans,
                "certificate_issuer_common_name": issuer,
                "certificate_not_after": _utc(not_after),
            }


def _head(*, secure: bool, path: str) -> tuple[int, dict[str, str]]:
    connection_type = http.client.HTTPSConnection if secure else http.client.HTTPConnection
    kwargs: dict[str, Any] = {"host": DOMAIN, "port": 443 if secure else 80, "timeout": 10}
    if secure:
        kwargs["context"] = ssl.create_default_context()
    connection = connection_type(**kwargs)
    try:
        connection.request("HEAD", path, headers={
            "Host": DOMAIN,
            "User-Agent": "fincilia-uat-edge-probe/1.0",
            "Accept": "text/html",
        })
        response = connection.getresponse()
        headers = {key.lower(): value for key, value in response.getheaders()}
        response.read()
        return response.status, headers
    finally:
        connection.close()


def _route(path: str) -> dict[str, Any]:
    status, all_headers = _head(secure=True, path=path)
    headers = {name: all_headers.get(name, "") for name in HEADER_NAMES}
    return {
        "path": path,
        "status": status,
        "headers": headers,
        "headers_sha256": hashlib.sha256(json.dumps(
            headers, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }


def probe_live(*, source_revision: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", source_revision) is None:
        raise EdgeProbeError("source revision must be a full lowercase Git SHA")
    http_status, http_headers = _head(secure=False, path="/")
    routes = [_route(path) for path in PUBLIC_PATHS]
    transport = {
        "http_status": http_status,
        "http_location": http_headers.get("location", ""),
        **_certificate(),
    }
    checks = {
        "certificate_covers_domain": DOMAIN in transport["certificate_san"],
        "certificate_trusted": transport["tls_verified"] is True,
        "csp_blocks_framing": all(
            "frame-ancestors 'none'" in route["headers"]["content-security-policy"]
            for route in routes
        ),
        "csp_forbids_unsafe_eval": all(
            "'unsafe-eval'" not in route["headers"]["content-security-policy"]
            for route in routes
        ),
        "http_redirect_exact": (
            http_status in {301, 308}
            and transport["http_location"] == f"https://{DOMAIN}/"
        ),
        "https_routes_ok": all(route["status"] == 200 for route in routes),
        "hsts_exact": all(
            route["headers"]["strict-transport-security"]
            == "max-age=31536000; includeSubDomains"
            for route in routes
        ),
        "no_store_exact": all(
            "no-store" in route["headers"]["cache-control"] for route in routes
        ),
        "nosniff_exact": all(
            route["headers"]["x-content-type-options"] == "nosniff"
            for route in routes
        ),
        "permissions_policy_exact": all(
            route["headers"]["permissions-policy"]
            == "camera=(), microphone=(), geolocation=(), payment=()"
            for route in routes
        ),
        "referrer_policy_exact": all(
            route["headers"]["referrer-policy"] == "strict-origin-when-cross-origin"
            for route in routes
        ),
        "tls_modern": transport["tls_version"] in {"TLSv1.2", "TLSv1.3"},
        "x_frame_options_exact": all(
            route["headers"]["x-frame-options"] == "DENY" for route in routes
        ),
    }
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "task_id": "FNC-UAT-003",
        "status": "passed",
        "domain": DOMAIN,
        "environment": "uat",
        "data_classification": "completely_synthetic",
        "observed_at": _utc(datetime.now(timezone.utc)),
        "source_revision": source_revision,
        "request_policy": {
            "methods": ["HEAD"],
            "authorization_sent": False,
            "body_sent_or_captured": False,
            "cookies_sent": False,
            "query_strings_sent": False,
        },
        "transport": transport,
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
    findings = validate_evidence(payload)
    if findings:
        raise EdgeProbeError("; ".join(findings))
    return payload


def validate_evidence(payload: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    required = {
        "schema_version", "task_id", "status", "domain", "environment",
        "data_classification", "observed_at", "source_revision", "request_policy",
        "transport", "routes", "checks", "probe_source_sha256",
        "independent_review", "real_data_authorized", "production_authorized",
        "evidence_sha256",
    }
    if set(payload) != required:
        findings.append("EDGE-SCHEMA")
    if (
        payload.get("schema_version") != "1.0.0"
        or payload.get("task_id") != "FNC-UAT-003"
        or payload.get("status") != "passed"
        or payload.get("domain") != DOMAIN
        or payload.get("environment") != "uat"
        or payload.get("data_classification") != "completely_synthetic"
        or payload.get("real_data_authorized") is not False
        or payload.get("production_authorized") is not False
    ):
        findings.append("EDGE-CLAIM")
    try:
        observed = datetime.fromisoformat(str(payload.get("observed_at")).replace("Z", "+00:00"))
        if observed.tzinfo is None or not str(payload.get("observed_at")).endswith("Z"):
            raise ValueError
    except ValueError:
        findings.append("EDGE-TIME")
    if re.fullmatch(r"[0-9a-f]{40}", str(payload.get("source_revision"))) is None:
        findings.append("EDGE-REVISION")
    if payload.get("request_policy") != {
        "methods": ["HEAD"],
        "authorization_sent": False,
        "body_sent_or_captured": False,
        "cookies_sent": False,
        "query_strings_sent": False,
    }:
        findings.append("EDGE-PRIVACY")

    transport = payload.get("transport")
    if not isinstance(transport, dict) or set(transport) != {
        "http_status", "http_location", "tls_verified", "tls_version", "cipher",
        "certificate_sha256", "certificate_san", "certificate_issuer_common_name",
        "certificate_not_after",
    }:
        findings.append("EDGE-TRANSPORT")
    else:
        if (
            transport.get("http_status") not in {301, 308}
            or transport.get("http_location") != f"https://{DOMAIN}/"
            or transport.get("tls_verified") is not True
            or transport.get("tls_version") not in {"TLSv1.2", "TLSv1.3"}
            or re.fullmatch(r"[0-9a-f]{64}", str(transport.get("certificate_sha256"))) is None
            or DOMAIN not in transport.get("certificate_san", [])
        ):
            findings.append("EDGE-TRANSPORT")

    routes = payload.get("routes")
    if (
        not isinstance(routes, list)
        or [item.get("path") for item in routes if isinstance(item, dict)] != list(PUBLIC_PATHS)
    ):
        findings.append("EDGE-ROUTES")
        routes = []
    for route in routes:
        headers = route.get("headers")
        if (
            set(route) != {"path", "status", "headers", "headers_sha256"}
            or route.get("status") != 200
            or not isinstance(headers, dict)
            or tuple(sorted(headers)) != tuple(sorted(HEADER_NAMES))
        ):
            findings.append("EDGE-ROUTE-SHAPE")
            continue
        observed_headers = hashlib.sha256(json.dumps(
            headers, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        if route.get("headers_sha256") != observed_headers:
            findings.append("EDGE-HEADER-DIGEST")
        csp = headers.get("content-security-policy", "")
        if (
            headers.get("strict-transport-security")
            != "max-age=31536000; includeSubDomains"
            or headers.get("x-content-type-options") != "nosniff"
            or headers.get("x-frame-options") != "DENY"
            or headers.get("referrer-policy") != "strict-origin-when-cross-origin"
            or headers.get("permissions-policy")
            != "camera=(), microphone=(), geolocation=(), payment=()"
            or "no-store" not in headers.get("cache-control", "")
            or "frame-ancestors 'none'" not in csp
            or "'unsafe-eval'" in csp
        ):
            findings.append("EDGE-HEADERS")

    checks = payload.get("checks")
    if (
        not isinstance(checks, dict)
        or set(checks) != EXPECTED_CHECKS
        or any(value is not True for value in checks.values())
    ):
        findings.append("EDGE-CHECKS")
    if payload.get("probe_source_sha256") != _source_digest():
        findings.append("EDGE-SOURCE")
    if payload.get("independent_review") != {
        "state": "pending",
        "required_roles": ["Security", "Platform/SRE", "QA"],
        "agent_observation_is_not_acceptance": True,
    }:
        findings.append("EDGE-REVIEW")
    if payload.get("evidence_sha256") != _canonical_digest(payload):
        findings.append("EDGE-EVIDENCE-DIGEST")
    return sorted(set(findings))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe the public Fincilia UAT edge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    live = subparsers.add_parser("probe", help="perform a read-only live probe")
    live.add_argument("--revision", required=True)
    validate = subparsers.add_parser("validate", help="validate durable evidence offline")
    validate.add_argument("--evidence", type=Path, default=EVIDENCE_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "probe":
            payload = probe_live(source_revision=args.revision)
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        payload = json.loads(args.evidence.read_text(encoding="utf-8"))
        findings = validate_evidence(payload)
        print(json.dumps({"findings": findings, "ok": not findings}, indent=2))
        return 0 if not findings else 1
    except (EdgeProbeError, OSError, ssl.SSLError, socket.timeout, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error), "ok": False}))
        return 2
