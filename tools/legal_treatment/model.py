"""Reglas ejecutables para una plantilla que ningún agente puede aprobar.

El validador no decide derecho. Comprueba que las preguntas que debe resolver
Legal siguen presentes, que el privacy-map queda cubierto dinámicamente y que
nadie convierte un placeholder en autorización de datos reales.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


REAL_GATES = frozenset({"DRG-00", "DRG-01"})
SECTION_IDS = frozenset({
    "SEC-PARTIES", "SEC-ROLES", "SEC-INSTRUCTIONS", "SEC-SCOPE", "SEC-DATA",
    "SEC-MINIMIZATION", "SEC-CONFIDENTIALITY", "SEC-SECURITY",
    "SEC-INCIDENTS", "SEC-RIGHTS", "SEC-RECIPIENTS", "SEC-RETENTION",
    "SEC-RESTORE", "SEC-AUDIT", "SEC-TERM", "SEC-SIGNATURES",
})
DECISION_IDS = frozenset({"UD-A-02", "UD-L-01", "UD-ROLE", "UD-PROVIDERS"})
GATE_IDS = frozenset({"A-02", "L-01", "DRG-00", "DRG-01"})
SIGNOFF_ROLES = frozenset({"Legal", "Privacy", "Security"})
ROLE_PENDING = "not_determined_pending_legal"
OFFICIAL_HOSTS = frozenset({
    "sic.gov.co",
    "www.sic.gov.co",
    "sedeelectronica.sic.gov.co",
    "www.suin-juriscol.gov.co",
})


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    path: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _finding(code: str, path: str, detail: str) -> Finding:
    return Finding(code, path, detail)


def _duplicates(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def _expected_activities(privacy: dict[str, Any]) -> dict[str, str]:
    activities = privacy.get("processing_activities")
    if not isinstance(activities, list):
        return {}
    expected: dict[str, str] = {}
    for item in activities:
        if not isinstance(item, dict) or item.get("target_gate") not in REAL_GATES:
            continue
        identifier, gate = item.get("id"), item.get("target_gate")
        if isinstance(identifier, str) and isinstance(gate, str):
            expected[identifier] = gate
    return expected


def validate(model: dict[str, Any], privacy: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    required_top = {
        "schema_version", "task_id", "status", "data_ceiling",
        "real_data_authorized", "legal_advice", "purpose", "source_contract",
        "official_sources", "required_sections", "activity_coverage",
        "blocking_decisions", "legal_decisions", "human_review",
        "required_signoffs", "gate_claims",
    }
    if set(model) != required_top:
        findings.append(_finding(
            "LEG-SCHEMA", "$", "top-level fields must match the reviewed contract"))
    if model.get("schema_version") != "1.0.0" or model.get("task_id") != "FNC-LEG-001":
        findings.append(_finding("LEG-IDENTITY", "$", "unsupported schema or task"))
    if model.get("status") != "review_pending":
        findings.append(_finding("LEG-STATUS", "$.status", "template must remain review_pending"))
    if model.get("data_ceiling") != "synthetic_only" or model.get("real_data_authorized") is not False:
        findings.append(_finding(
            "LEG-REAL-DATA", "$.data_ceiling", "this artifact cannot authorize real data"))
    if model.get("legal_advice") is not False:
        findings.append(_finding(
            "LEG-ADVICE", "$.legal_advice", "an agent-generated template is not legal advice"))
    if not isinstance(model.get("purpose"), str) or len(model["purpose"].strip()) < 40:
        findings.append(_finding("LEG-PURPOSE", "$.purpose", "purpose must be explicit"))

    source_contract = model.get("source_contract")
    if source_contract != {
        "path": "docs/privacy/privacy-map.json",
        "activity_selector": "target_gate in [DRG-00, DRG-01]",
        "decision_selector": "id in [UD-A-02, UD-L-01, UD-ROLE, UD-PROVIDERS]",
    }:
        findings.append(_finding(
            "LEG-SOURCE-CONTRACT", "$.source_contract", "privacy source contract drifted"))

    sources = model.get("official_sources")
    if not isinstance(sources, list) or len(sources) < 3:
        findings.append(_finding(
            "LEG-SOURCES", "$.official_sources", "at least three official sources are required"))
    else:
        ids = [str(item.get("id")) for item in sources if isinstance(item, dict)]
        if len(ids) != len(sources) or _duplicates(ids):
            findings.append(_finding(
                "LEG-SOURCE-ID", "$.official_sources", "source identifiers must be unique"))
        for index, item in enumerate(sources):
            path = f"$.official_sources[{index}]"
            if not isinstance(item, dict):
                findings.append(_finding("LEG-SOURCE", path, "source must be an object"))
                continue
            if item.get("authority") not in {"SIC", "SUIN"}:
                findings.append(_finding("LEG-SOURCE-AUTHORITY", path, "source is not official"))
            expected_source_fields = {
                "id", "authority", "kind", "title", "url", "consulted_at", "use",
            }
            if set(item) != expected_source_fields:
                findings.append(_finding(
                    "LEG-SOURCE-SCHEMA", path, "source fields must match the reviewed allowlist"))
            parsed = urlparse(str(item.get("url", "")))
            if (parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS
                    or parsed.username is not None or parsed.password is not None
                    or parsed.port is not None):
                findings.append(_finding("LEG-SOURCE-URL", path, "source URL is not an allowed authority"))
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(item.get("consulted_at", ""))):
                findings.append(_finding("LEG-SOURCE-DATE", path, "consultation date is required"))
            if not isinstance(item.get("use"), str) or len(item["use"].strip()) < 25:
                findings.append(_finding("LEG-SOURCE-USE", path, "source use must be explained"))
            if any(key in item for key in ("quote", "full_text", "legal_conclusion")):
                findings.append(_finding("LEG-SOURCE-OVERREACH", path, "source may not embed conclusions or copied text"))

    sections = model.get("required_sections")
    if not isinstance(sections, list):
        findings.append(_finding("LEG-SECTIONS", "$.required_sections", "sections must be a list"))
    else:
        ids = [str(item.get("id")) for item in sections if isinstance(item, dict)]
        if set(ids) != SECTION_IDS or len(ids) != len(SECTION_IDS):
            findings.append(_finding(
                "LEG-SECTION-COVERAGE", "$.required_sections", "required legal sections are missing, extra or duplicated"))
        for index, item in enumerate(sections):
            path = f"$.required_sections[{index}]"
            if not isinstance(item, dict):
                findings.append(_finding("LEG-SECTION", path, "section must be an object"))
                continue
            if set(item) != {"id", "title", "owner", "state", "prompt"}:
                findings.append(_finding("LEG-SECTION-SCHEMA", path, "section fields drifted"))
            if item.get("state") != "pending_legal":
                findings.append(_finding("LEG-SECTION-STATE", path, "section cannot be pre-approved"))
            if item.get("owner") not in {"Legal", "Privacy", "Security"}:
                findings.append(_finding("LEG-SECTION-OWNER", path, "section needs a known reviewer role"))
            if not isinstance(item.get("prompt"), str) or len(item["prompt"].strip()) < 40:
                findings.append(_finding("LEG-SECTION-PROMPT", path, "section prompt is incomplete"))

    expected = _expected_activities(privacy)
    if not expected:
        findings.append(_finding(
            "LEG-PRIVACY-SOURCE", "privacy.processing_activities", "no real-data activities were discovered"))
    coverage = model.get("activity_coverage")
    if not isinstance(coverage, list):
        findings.append(_finding("LEG-ACTIVITIES", "$.activity_coverage", "coverage must be a list"))
    else:
        ids = [str(item.get("activity_id")) for item in coverage if isinstance(item, dict)]
        if set(ids) != set(expected) or len(ids) != len(expected):
            findings.append(_finding(
                "LEG-ACTIVITY-COVERAGE", "$.activity_coverage",
                "coverage must equal the dynamic DRG-00/DRG-01 activity set"))
        for index, item in enumerate(coverage):
            path = f"$.activity_coverage[{index}]"
            if not isinstance(item, dict):
                findings.append(_finding("LEG-ACTIVITY", path, "activity must be an object"))
                continue
            if set(item) != {"activity_id", "target_gate", "contract_applicability", "fincilia_role"}:
                findings.append(_finding("LEG-ACTIVITY-SCHEMA", path, "activity fields drifted"))
            identifier = item.get("activity_id")
            if identifier in expected and item.get("target_gate") != expected[identifier]:
                findings.append(_finding("LEG-ACTIVITY-GATE", path, "activity gate differs from privacy-map"))
            if item.get("contract_applicability") != "pending_legal":
                findings.append(_finding("LEG-APPLICABILITY", path, "contract applicability needs Legal"))
            if item.get("fincilia_role") != ROLE_PENDING:
                findings.append(_finding("LEG-ROLE", path, "Fincilia role is not yet adjudicated"))

    privacy_decisions = {
        str(item.get("id")): item for item in privacy.get("unresolved_decisions", [])
        if isinstance(item, dict) and item.get("id") in DECISION_IDS
    }
    decisions = model.get("blocking_decisions")
    if not isinstance(decisions, list):
        findings.append(_finding("LEG-DECISIONS", "$.blocking_decisions", "decisions must be a list"))
    else:
        ids = [str(item.get("id")) for item in decisions if isinstance(item, dict)]
        if set(ids) != DECISION_IDS or len(ids) != len(DECISION_IDS) or set(privacy_decisions) != DECISION_IDS:
            findings.append(_finding(
                "LEG-DECISION-COVERAGE", "$.blocking_decisions", "blocking decision coverage drifted"))
        for index, item in enumerate(decisions):
            path = f"$.blocking_decisions[{index}]"
            if not isinstance(item, dict) or set(item) != {"id", "state", "selected_value"}:
                findings.append(_finding("LEG-DECISION-SCHEMA", path, "decision fields drifted"))
                continue
            if item.get("state") != "open" or item.get("selected_value") is not None:
                findings.append(_finding("LEG-DECISION-PREMATURE", path, "decision must remain open and unselected"))

    legal = model.get("legal_decisions")
    empty_legal = {
        "fincilia_role": None, "legal_basis": None, "controller_party": None,
        "processor_party": None, "region": None, "provider": None,
        "subprocessors": [], "retention_durations": {},
    }
    if legal != empty_legal:
        findings.append(_finding(
            "LEG-CONCLUSION-PREMATURE", "$.legal_decisions", "legal decisions need nominal human adjudication"))

    review = model.get("human_review")
    expected_review = {
        "state": "pending_distinct_lawyer", "reviewer_id": None,
        "professional_basis": None, "approved_at": None,
        "approval_evidence_ref": None,
    }
    if review != expected_review:
        findings.append(_finding(
            "LEG-HUMAN-REVIEW", "$.human_review", "no lawyer approval is recorded"))

    signoffs = model.get("required_signoffs")
    if not isinstance(signoffs, list):
        findings.append(_finding("LEG-SIGNOFFS", "$.required_signoffs", "signoffs must be a list"))
    else:
        roles = [str(item.get("role")) for item in signoffs if isinstance(item, dict)]
        if set(roles) != SIGNOFF_ROLES or len(roles) != len(SIGNOFF_ROLES):
            findings.append(_finding("LEG-SIGNOFF-COVERAGE", "$.required_signoffs", "required reviewers drifted"))
        for index, item in enumerate(signoffs):
            if (not isinstance(item, dict)
                    or set(item) != {"role", "reviewer_id", "state"}
                    or item.get("state") != "pending"
                    or item.get("reviewer_id") is not None):
                findings.append(_finding(
                    "LEG-SIGNOFF-PREMATURE", f"$.required_signoffs[{index}]", "signoff is not pending"))

    claims = model.get("gate_claims")
    if not isinstance(claims, list):
        findings.append(_finding("LEG-GATES", "$.gate_claims", "gate claims must be a list"))
    else:
        ids = [str(item.get("id")) for item in claims if isinstance(item, dict)]
        if set(ids) != GATE_IDS or len(ids) != len(GATE_IDS):
            findings.append(_finding("LEG-GATE-COVERAGE", "$.gate_claims", "gate inventory drifted"))
        for index, item in enumerate(claims):
            if (not isinstance(item, dict)
                    or set(item) != {"id", "status", "authorized"}
                    or item.get("status") != "not_met"
                    or item.get("authorized") is not False):
                findings.append(_finding(
                    "LEG-GATE-PREMATURE", f"$.gate_claims[{index}]", "template cannot meet or authorize a gate"))
    return sorted(set(findings))


def report(model: dict[str, Any], privacy: dict[str, Any]) -> dict[str, Any]:
    findings = validate(model, privacy)
    expected = _expected_activities(privacy)
    return {
        "ok": not findings,
        "model_valid": not findings,
        "ready_for_lawyer_review": not findings,
        "real_data_authorized": False,
        "human_approval": False,
        "covered_activities": len(expected),
        "activities_by_gate": {
            gate: sum(1 for value in expected.values() if value == gate)
            for gate in sorted(REAL_GATES)
        },
        "pending_sections": len(SECTION_IDS),
        "blocking_decisions": sorted(DECISION_IDS),
        "required_signoffs": sorted(SIGNOFF_ROLES),
        "aggregate_score": None,
        "findings": [item.as_dict() for item in findings],
    }
