from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_PLANES = {"postgresql_domain","object_quarantine","object_raw","object_derived","object_exports","security_archive_delete_ledger","backup_and_wal","queue_and_workflow_history","secrets_and_kms_metadata","telemetry_and_support","identity_and_notifications","analytics_projection","ai_gateway_and_provider"}
REQUIRED_GATES = {f"A02-G{number:02d}" for number in range(1, 11)}
REQUIRED_POSTURE = {"deployment":"local_synthetic_only","real_data":"forbidden","external_egress":"deny","external_ai":"forbidden","cross_region_replication":"forbidden"}

@dataclass(frozen=True, order=True)
class Finding:
    code: str
    location: str
    message: str
    def as_dict(self) -> dict[str,str]: return {"code":self.code,"location":self.location,"message":self.message}

def validate(model: dict[str,Any], privacy: dict[str,Any]) -> list[Finding]:
    findings: list[Finding] = []
    def fail(code:str, location:str, message:str): findings.append(Finding(code,location,message))
    if model.get("decision_status") != "pending_human_review" or model.get("human_acceptance") is not False: fail("A02-HUMAN-PENDING","decision_status","agents cannot accept A-02")
    if privacy.get("region_decision") != "pending_A-02": fail("A02-PRIVACY-ALIGNMENT","privacy-map.json","privacy decision must remain pending_A-02")
    if model.get("default_posture") != REQUIRED_POSTURE: fail("A02-DEFAULT-DENY","default_posture","local-only deny posture drifted")
    sources = {source.get("id"): source for source in model.get("sources",[])}
    if len(sources) != len(model.get("sources",[])): fail("A02-SOURCE-DUPLICATE","sources","source IDs must be unique")
    for source_id, source in sources.items():
        if not str(source.get("url","")).startswith("https://"): fail("A02-SOURCE-OFFICIAL",source_id,"source requires HTTPS official URL")
        if source.get("authority") not in {"SIC Colombia","AWS","Microsoft","Google Cloud"}: fail("A02-SOURCE-OFFICIAL",source_id,"unknown authority")
    candidates = model.get("candidate_locations",[])
    if not candidates: fail("A02-CANDIDATES","candidate_locations","shortlist cannot be empty")
    for candidate in candidates:
        location = candidate.get("id","candidate")
        if candidate.get("selected") is not False: fail("A02-PREMATURE-SELECTION",location,"candidate cannot be selected")
        if candidate.get("legal_suitability") != "unknown_requires_legal": fail("A02-LEGAL-UNKNOWN",location,"legal suitability stays unknown")
        if candidate.get("service_matrix_status") != "unverified": fail("A02-SERVICE-UNKNOWN",location,"service matrix stays unverified")
        if not candidate.get("source_ids") or any(source not in sources for source in candidate.get("source_ids",[])): fail("A02-SOURCE-REFERENCE",location,"candidate source missing or unknown")
    inference = model.get("location_inference",{})
    if inference.get("colombia_full_public_cloud_region_evidenced") is not False or inference.get("reverify_before_decision") is not True or inference.get("edge_or_local_zone_counts_as_full_region") is not False: fail("A02-LOCATION-INFERENCE","location_inference","location inference must remain scoped and reverified")
    if set(model.get("data_planes",[])) != REQUIRED_PLANES: fail("A02-DATA-PLANES","data_planes","all data planes must be evaluated")
    contract = model.get("service_location_contract",{})
    required_fields = set(contract.get("required_fields",[]))
    for field in {"primary_processing_location","at_rest_location","backup_location","disaster_recovery_location","control_plane_location","support_access_locations","subprocessor_locations","deletion_propagation","portability_format"}:
        if field not in required_fields: fail("A02-SERVICE-FIELD","service_location_contract",f"missing {field}")
    if contract.get("all_planes_state") != "unknown_blocks_cloud": fail("A02-UNKNOWN-BLOCKS","service_location_contract","unknown must block cloud")
    gates = model.get("decision_gates",[]); gate_ids = {gate.get("id") for gate in gates}
    if gate_ids != REQUIRED_GATES or len(gates) != len(REQUIRED_GATES): fail("A02-GATE-COVERAGE","decision_gates","A02-G01..G10 required exactly once")
    for gate in gates:
        if gate.get("state") != "not_met": fail("A02-GATE-PREMATURE",gate.get("id","gate"),"gate cannot be met by agent")
        if not gate.get("owner") or not gate.get("reviewer") or gate.get("owner") == gate.get("reviewer"): fail("A02-GATE-SOD",gate.get("id","gate"),"owner and reviewer must be independent")
        if not gate.get("evidence"): fail("A02-GATE-EVIDENCE",gate.get("id","gate"),"evidence contract required")
    scoring = model.get("scoring_policy",{})
    if scoring.get("scores_allowed_before_gates_G01_to_G06") is not False or scoring.get("winner") is not None: fail("A02-FALSE-PRECISION","scoring_policy","winner and scores are forbidden before gates")
    if sum(item.get("weight",0) for item in scoring.get("dimensions",[])) != 100: fail("A02-WEIGHTS","scoring_policy","weights must total 100")
    for rule in ["edge_locations_never_store_raw_financial_evidence","no_cross_region_replication_without_explicit_legal_and_service_review","backup_restore_reapplies_delete_ledger_before_service_reopens"]:
        if rule not in model.get("architecture_constraints",[]): fail("A02-ARCH-CONSTRAINT","architecture_constraints",f"missing {rule}")
    return sorted(set(findings))

def validate_repository(root:Path) -> list[Finding]:
    model=json.loads((root/"docs/architecture/region-transmission-decision.json").read_text(encoding="utf-8"))
    privacy=json.loads((root/"docs/privacy/privacy-map.json").read_text(encoding="utf-8"))
    return validate(model,privacy)
