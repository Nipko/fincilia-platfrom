from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


PINNED_POSTGRES = "postgres:17.11-alpine3.24@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73"


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def validate_compose(text: str) -> list[Finding]:
    findings: list[Finding] = []
    images = re.findall(r"(?m)^\s+image:\s+(\S+)\s*$", text)
    if images != [PINNED_POSTGRES, PINNED_POSTGRES]:
        findings.append(Finding("LOCAL-IMAGE-PIN", "both services must use the approved immutable PostgreSQL artifact"))
    ports = re.findall(r'(?m)^\s+-\s+"([^\n]+:\d+)"\s*$', text)
    if len(ports) != 1 or not ports[0].startswith("127.0.0.1:"):
        findings.append(Finding("LOCAL-LOOPBACK", "exactly one loopback-only port is allowed"))
    if "healthcheck:" not in text or "pg_isready" not in text:
        findings.append(Finding("LOCAL-HEALTHCHECK", "PostgreSQL healthcheck is required"))
    if "fincilia_local_pgdata:/var/lib/postgresql/data" not in text or "name: fincilia_local_pgdata" not in text:
        findings.append(Finding("LOCAL-NAMED-VOLUME", "explicit named persistence volume is required"))
    if "internal: true" not in text:
        findings.append(Finding("LOCAL-INTERNAL-NETWORK", "local service network must deny external routing"))
    if "profiles: [\"test\"]" not in text or "lifecycle-test:" not in text:
        findings.append(Finding("LOCAL-TEST-PROFILE", "ephemeral lifecycle runner must be profile-gated"))
    if "privileged: true" in text or "network_mode: host" in text:
        findings.append(Finding("LOCAL-PRIVILEGE", "privileged or host-network containers are forbidden"))
    if "./db/init:/docker-entrypoint-initdb.d:ro" not in text or "./scripts:/checks:ro" not in text:
        findings.append(Finding("LOCAL-READONLY-MOUNTS", "bootstrap and checks must be mounted read-only"))
    if "synthetic" not in text.lower():
        findings.append(Finding("LOCAL-DATA-CEILING", "synthetic-only marker is required"))
    return sorted(set(findings))


def validate_bootstrap(text: str) -> list[Finding]:
    findings: list[Finding] = []
    required = ["NOSUPERUSER", "NOBYPASSRLS", "NOCREATEDB", "NOCREATEROLE", "REVOKE CREATE ON SCHEMA public", "synthetic_only"]
    for token in required:
        if token not in text:
            findings.append(Finding("LOCAL-BOOTSTRAP-HARDENING", f"missing {token}"))
    forbidden = ["CREATE EXTENSION", "COPY "]
    for token in forbidden:
        if token in text:
            findings.append(Finding("LOCAL-BOOTSTRAP-FORBIDDEN", f"forbidden bootstrap token {token}"))
    if re.search(r"(?m)^\s+SUPERUSER\s*$", text) or re.search(r"(?m)^\s+BYPASSRLS\s*;?\s*$", text):
        findings.append(Finding("LOCAL-BOOTSTRAP-PRIVILEGE", "application role cannot bypass controls"))
    return sorted(set(findings))


def validate_repository(root: Path) -> list[Finding]:
    compose = (root / "infra/local/compose.yaml").read_text(encoding="utf-8")
    bootstrap = (root / "infra/local/db/init/001_bootstrap.sql").read_text(encoding="utf-8")
    return sorted(set(validate_compose(compose) + validate_bootstrap(bootstrap)))
