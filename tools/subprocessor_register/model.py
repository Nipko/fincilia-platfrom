from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


EXPECTED_PROVIDERS = {"AWS", "GOOGLE", "CLOUDFLARE", "NAMECHEAP", "GITHUB"}
EXPECTED_SCOPES = {"openid", "email", "profile"}
ALLOWED_SOURCE_HOSTS = {
    "aws.amazon.com",
    "developers.google.com",
    "docs.aws.amazon.com",
    "docs.github.com",
    "sedeelectronica.sic.gov.co",
    "www.cloudflare.com",
    "www.funcionpublica.gov.co",
    "www.namecheap.com",
}
EXPECTED_GATES = {"A-02", "DRG-00", "DRG-01"}
PENDING_LEGAL = "pending_independent_legal_review"


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "location": self.location, "message": self.message}


def validate(model: dict[str, Any], public_disclosure: str) -> list[Finding]:
    findings: list[Finding] = []

    def fail(code: str, location: str, message: str) -> None:
        findings.append(Finding(code, location, message))

    if model.get("status") != "review_pending" or model.get("legal_advice") is not False:
        fail("SPR-HUMAN-PENDING", "status", "technical inventory cannot approve legal review")
    if (model.get("data_ceiling") != "synthetic_only_until_gate"
            or model.get("real_data_authorized") is not False):
        fail("SPR-REAL-DATA", "data_ceiling", "real data must remain unauthorized")
    scope = model.get("scope", {})
    if scope.get("external_ai_enabled") is not False:
        fail("SPR-EXTERNAL-AI", "scope.external_ai_enabled", "external AI must remain disabled")
    if scope.get("email_ingestion_enabled") is not False:
        fail("SPR-EMAIL-INGEST", "scope.email_ingestion_enabled", "email ingestion must remain disabled")

    sources_list = model.get("sources", [])
    sources = {item.get("id"): item for item in sources_list if isinstance(item, dict)}
    if len(sources) != len(sources_list) or not sources:
        fail("SPR-SOURCE-UNIQUE", "sources", "source IDs must be unique and non-empty")
    for source_id, source in sources.items():
        location = f"sources.{source_id}"
        parsed = urlsplit(str(source.get("url", "")))
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.hostname not in ALLOWED_SOURCE_HOSTS):
            fail("SPR-SOURCE-OFFICIAL", location, "source must use an allowlisted official HTTPS host")
        try:
            retrieved = date.fromisoformat(str(source.get("retrieved_at", "")))
            version = date.fromisoformat(str(model.get("version", "")))
            if retrieved > version:
                fail("SPR-SOURCE-DATE", location, "source cannot be retrieved after register version")
        except ValueError:
            fail("SPR-SOURCE-DATE", location, "source and register dates must be ISO dates")

    providers_list = model.get("providers", [])
    providers = {item.get("id"): item for item in providers_list if isinstance(item, dict)}
    if (set(providers) != EXPECTED_PROVIDERS
            or len(providers) != len(EXPECTED_PROVIDERS)
            or len(providers_list) != len(EXPECTED_PROVIDERS)
            or any(not isinstance(item, dict) for item in providers_list)):
        fail("SPR-PROVIDER-SET", "providers", "the five reviewed providers are required exactly once")
    for provider_id, provider in providers.items():
        if provider.get("currently_receives_real_financial_data") is not False:
            fail("SPR-PROVIDER-REAL-DATA", provider_id, "no provider may receive real financial data yet")
        refs = provider.get("source_ids", [])
        if not refs or any(ref not in sources for ref in refs):
            fail("SPR-SOURCE-REFERENCE", provider_id, "provider source is missing or unknown")
        if "pending" not in str(provider.get("role_state", "")):
            fail("SPR-ROLE-PENDING", provider_id, "provider role requires independent legal review")

    aws = providers.get("AWS", {})
    if (aws.get("plane") != "product_runtime" or aws.get("service_region") != "sa-east-1"
            or aws.get("service_region_meaning") != "regional_resources_only"):
        fail("SPR-AWS-REGION", "AWS", "AWS regional scope must stay exact and qualified")
    if aws.get("financial_document_path") != "blocked_until_DRG-01":
        fail("SPR-AWS-DATA-GATE", "AWS", "financial document path must remain gate-blocked")
    if aws.get("support_and_control_plane_location") != "requires_independent_review":
        fail("SPR-AWS-GLOBAL-PLANE", "AWS", "support and control-plane location cannot be inferred")

    google = providers.get("GOOGLE", {})
    if set(google.get("oidc_scopes", [])) != EXPECTED_SCOPES:
        fail("SPR-GOOGLE-SCOPES", "GOOGLE", "Google scopes must be openid, email and profile only")
    if google.get("durable_identity_key") != "sub":
        fail("SPR-GOOGLE-SUB", "GOOGLE", "Google sub is the only durable identity key")
    for prohibited in ("financial_document", "Gmail", "Google_Drive", "contacts", "calendars"):
        if prohibited not in google.get("prohibited_data", []):
            fail("SPR-GOOGLE-BOUNDARY", "GOOGLE", f"missing prohibited Google data: {prohibited}")

    cloudflare = providers.get("CLOUDFLARE", {})
    if cloudflare.get("plane") != "authoritative_dns" or cloudflare.get("application_proxy_enabled") is not False:
        fail("SPR-CLOUDFLARE-BOUNDARY", "CLOUDFLARE", "Cloudflare must remain DNS-only in this inventory")
    namecheap = providers.get("NAMECHEAP", {})
    if (namecheap.get("plane") != "contact_email"
            or namecheap.get("email_ingestion_to_product_enabled") is not False):
        fail("SPR-NAMECHEAP-BOUNDARY", "NAMECHEAP", "Namecheap must remain contact-email only")
    github = providers.get("GITHUB", {})
    if github.get("plane") != "development_supply_chain" or github.get("runtime_data_path") is not False:
        fail("SPR-GITHUB-BOUNDARY", "GITHUB", "GitHub must remain outside the runtime data path")

    legal = model.get("legal_review", {})
    for field in (
        "classification_by_activity", "international_transmission_mechanism",
        "dpa_sufficiency", "subprocessor_objection_process",
    ):
        if legal.get(field) != PENDING_LEGAL:
            fail("SPR-LEGAL-PENDING", f"legal_review.{field}", "legal decision must remain pending")
    for field in ("reviewer_id", "reviewed_at", "evidence_ref"):
        if legal.get(field) is not None:
            fail("SPR-LEGAL-IDENTITY", f"legal_review.{field}", "no review may be invented")

    gates = model.get("gate_claims", [])
    if {item.get("id") for item in gates if isinstance(item, dict)} != EXPECTED_GATES:
        fail("SPR-GATE-SET", "gate_claims", "A-02, DRG-00 and DRG-01 are required")
    for gate in gates:
        if gate.get("status") != "not_met" or gate.get("authorized") is not False:
            fail("SPR-GATE-PREMATURE", str(gate.get("id", "gate")), "register cannot open a gate")

    for name in ("Amazon Web Services", "Google LLC", "Namecheap", "Cloudflare"):
        if name not in public_disclosure:
            fail("SPR-PUBLIC-DISCLOSURE", "public_disclosure", f"public page is missing {name}")
    return sorted(set(findings))


def report(model: dict[str, Any], public_disclosure: str) -> dict[str, Any]:
    findings = validate(model, public_disclosure)
    return {
        "ok": not findings,
        "provider_count": len(model.get("providers", [])),
        "source_count": len(model.get("sources", [])),
        "ready_for_independent_review": not findings,
        "human_approval": False,
        "real_data_authorized": False,
        "findings": [finding.as_dict() for finding in findings],
    }


def validate_repository(root: Path) -> list[Finding]:
    import json

    model = json.loads((root / "docs/legal/subprocessor-register.json").read_text(encoding="utf-8"))
    public = (root / model["public_disclosure_path"]).read_text(encoding="utf-8")
    return validate(model, public)
