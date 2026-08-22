from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path("docs/integrations/provider-evaluation.json")
OFFICIAL_HOSTS = {
    "soportedevs.bancolombia.com", "www.bancolombia.com",
    "docs.prometeoapi.com", "developers.belvo.com",
}


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


def validate_model(model: dict[str, Any], root: Path = ROOT) -> list[Finding]:
    findings: list[Finding] = []
    top = {"schema_version", "task", "status", "evidence_checked_at", "data_ceiling", "production_connections_allowed", "human_acceptance", "agent_may_select_vendor", "platform_never_receives_bank_credentials", "permanent_fallback", "required_candidates", "scoring", "candidates", "rfq", "gates"}
    if set(model) != top:
        findings.append(Finding("INT-SCHEMA", "model", f"keys={sorted(set(model))}"))
        return findings
    if model["data_ceiling"] != "synthetic_only" or model["production_connections_allowed"] is not False:
        findings.append(Finding("INT-DATA-GATE", "model", "production or real data enabled"))
    if model["human_acceptance"] != "pending" or model["agent_may_select_vendor"] is not False:
        findings.append(Finding("INT-HUMAN", "model", "vendor selection requires human approval"))
    if model["platform_never_receives_bank_credentials"] is not True:
        findings.append(Finding("INT-CREDENTIAL", "model", "bank credentials boundary disabled"))
    if model["permanent_fallback"] != "file_ingestion":
        findings.append(Finding("INT-FALLBACK", "model", "file ingestion must remain permanent"))

    weights = model["scoring"].get("weights", {})
    if sum(weights.values()) != 100 or set(model["scoring"]) != {"weights", "minimum_evidence", "winner"}:
        findings.append(Finding("INT-SCORING", "scoring", "weights/keys invalid"))
    if model["scoring"]["winner"] is not None:
        findings.append(Finding("INT-WINNER", "scoring", "winner selected before gates"))
    if len(model["scoring"]["minimum_evidence"]) < 10:
        findings.append(Finding("INT-EVIDENCE", "scoring", "minimum evidence weakened"))

    required = set(model["required_candidates"])
    candidates = model["candidates"]
    ids = [candidate.get("id") for candidate in candidates]
    if set(ids) != required or len(ids) != len(set(ids)):
        findings.append(Finding("INT-COVERAGE", "candidates", f"required={sorted(required)} actual={sorted(set(ids))}"))
    candidate_keys = {"id", "kind", "countries", "business_coverage", "coverage_evidence", "access_method", "credential_posture", "sandbox", "production_state", "quote_state", "sla_state", "score", "gaps", "sources"}
    for candidate in candidates:
        identifier = candidate.get("id", "<missing>")
        if set(candidate) != candidate_keys:
            findings.append(Finding("INT-CANDIDATE-SCHEMA", identifier, "candidate keys must be exact"))
            continue
        if candidate["score"] is not None:
            findings.append(Finding("INT-PREMATURE-SCORE", identifier, "score requires complete evidence"))
        if not candidate["sources"] or not candidate["gaps"]:
            findings.append(Finding("INT-EVIDENCE", identifier, "sources and gaps required"))
        if "required" not in candidate["production_state"] and "blocked" not in candidate["production_state"] and "not_a_" not in candidate["production_state"]:
            findings.append(Finding("INT-PRODUCTION", identifier, candidate["production_state"]))
        if identifier != "file_ingestion" and candidate["quote_state"] == "received":
            findings.append(Finding("INT-QUOTE", identifier, "unverified quote claim"))
        for source in candidate["sources"]:
            if source.startswith("http"):
                parsed = urlparse(source)
                if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
                    findings.append(Finding("INT-SOURCE", identifier, source))
            else:
                path = Path(source)
                if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                    findings.append(Finding("INT-SOURCE", identifier, source))

    by_id = {candidate["id"]: candidate for candidate in candidates if set(candidate) == candidate_keys}
    if by_id.get("file_ingestion", {}).get("kind") != "permanent_fallback":
        findings.append(Finding("INT-FALLBACK", "file_ingestion", "not permanent"))
    belvo = by_id.get("belvo", {})
    if belvo.get("countries") or belvo.get("business_coverage") != "not_publicly_supported_for_colombia_banking":
        findings.append(Finding("INT-BELVO", "belvo", "public Colombia banking support overstated"))
    for identifier in ("bancolombia_direct", "prometeo"):
        if by_id.get(identifier, {}).get("business_coverage") != "candidate_not_contractually_verified":
            findings.append(Finding("INT-COVERAGE-CLAIM", identifier, "coverage overstated"))

    rfq = model["rfq"]
    if set(rfq) != {"minimum_comparable_quotes", "received_quotes", "targets", "human_outreach_required", "outreach_authorized", "comparison_currency", "tax_treatment", "fx_scenarios_percent"}:
        findings.append(Finding("INT-RFQ-SCHEMA", "rfq", "rfq keys invalid"))
    if rfq.get("minimum_comparable_quotes") != 3 or rfq.get("received_quotes") != 0:
        findings.append(Finding("INT-QUOTE", "rfq", "three quotes remain pending"))
    if rfq.get("human_outreach_required") is not True or rfq.get("outreach_authorized") is not False:
        findings.append(Finding("INT-OUTREACH", "rfq", "external outreach cannot be agent-authorized"))
    if rfq.get("comparison_currency") != "COP" or rfq.get("tax_treatment") != "separate" or rfq.get("fx_scenarios_percent") != [-25, -10, 0, 10, 25]:
        findings.append(Finding("INT-COST", "rfq", "cost comparison controls weakened"))

    gates = model["gates"]
    if len({gate.get("id") for gate in gates}) != len(gates):
        findings.append(Finding("INT-GATE", "gates", "duplicate gate"))
    for gate in gates:
        if set(gate) != {"id", "state", "rule"} or gate["state"] not in {"met", "not_met"}:
            findings.append(Finding("INT-GATE", str(gate.get("id")), "invalid gate"))
        if gate["id"] != "INT-G01" and gate["state"] != "not_met":
            findings.append(Finding("INT-GATE", gate["id"], "external gate prematurely met"))
    return findings


def validate_repository(root: Path = ROOT, model_override: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[Finding]]:
    model = model_override or json.loads((root / MODEL_PATH).read_text(encoding="utf-8"))
    findings = validate_model(model, root)
    report = {
        "candidate_count": len(model.get("candidates", [])),
        "quotes_received": model.get("rfq", {}).get("received_quotes"),
        "quotes_required": model.get("rfq", {}).get("minimum_comparable_quotes"),
        "gates_not_met": sorted(gate["id"] for gate in model.get("gates", []) if gate.get("state") == "not_met"),
        "winner": model.get("scoring", {}).get("winner"),
    }
    return report, findings


def main() -> int:
    report, findings = validate_repository()
    print(json.dumps({"ok": not findings, "report": report, "errors": [finding.as_dict() for finding in findings]}, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
