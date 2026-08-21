from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_ZONES = {f"Z{index}" for index in range(7)}
REQUIRED_CLASSES = {
    "public",
    "internal",
    "confidential",
    "financial_sensitive",
    "secret",
    "prohibited",
}
REQUIRED_FLOWS = {f"F{index:02d}" for index in range(1, 14)}
REQUIRED_STORES = {
    "postgresql",
    "object_storage_quarantine",
    "object_storage_raw",
    "object_storage_derived",
    "temporal",
    "valkey",
    "analytics_projection",
    "security_archive",
    "vault",
}
REQUIRED_LOG_DENYLIST = {
    "payload",
    "raw_content",
    "original_filename",
    "cell_value",
    "ocr_text",
    "amount",
    "account_number",
    "tax_id",
    "financial_reference",
    "token",
    "credential",
    "secret",
}
COMPANY_SCOPES = {
    "not_applicable_until_resource_resolution",
    "required_verified",
    "preserved_verified",
    "preserved_verified_or_explicit_platform_scope",
}
EGRESS_MODES = {"none", "external_ingress", "user_delivery", "approved_gateway"}


@dataclass(frozen=True, order=True)
class DfdError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _catalog_ids(model: dict[str, Any], key: str, errors: list[DfdError]) -> set[str]:
    catalog = model.get(key)
    if not isinstance(catalog, list) or not catalog:
        errors.append(DfdError("DFD-CATALOG", key, "catalog must be a non-empty list"))
        return set()
    identifiers = [item.get("id") for item in catalog if isinstance(item, dict)]
    valid = {item for item in identifiers if isinstance(item, str) and item}
    if len(valid) != len(identifiers):
        errors.append(DfdError("DFD-CATALOG-ID", key, "every catalog item requires a non-empty id"))
    for duplicate in _duplicates([item for item in identifiers if isinstance(item, str)]):
        errors.append(DfdError("DFD-CATALOG-DUPLICATE", f"{key}.{duplicate}", "catalog id is duplicated"))
    return valid


def _require_text(flow: dict[str, Any], flow_id: str, key: str, errors: list[DfdError]) -> None:
    value = flow.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(DfdError("DFD-FLOW-FIELD", f"flows.{flow_id}.{key}", "non-empty text is required"))


def _has_store(flow: dict[str, Any], store: str) -> bool:
    return any(
        isinstance(item, dict) and item.get("store") == store
        for item in flow.get("persistence", [])
    )


def _require_controls(
    flow: dict[str, Any], flow_id: str, required: set[str], errors: list[DfdError]
) -> None:
    present = set(flow.get("controls", []))
    for missing in sorted(required - present):
        errors.append(
            DfdError("DFD-SPECIAL-CONTROL", f"flows.{flow_id}.controls", f"{missing} is required")
        )


def validate_model(model: dict[str, Any]) -> list[DfdError]:
    errors: list[DfdError] = []
    if model.get("schema_version") != 1:
        errors.append(DfdError("DFD-SCHEMA-VERSION", "$", "schema_version must equal 1"))
    if model.get("task_id") != "FNC-ARC-002":
        errors.append(DfdError("DFD-TASK", "task_id", "task_id must be FNC-ARC-002"))
    if model.get("data_ceiling") != "synthetic_only":
        errors.append(DfdError("DFD-DATA-CEILING", "data_ceiling", "E0 permits synthetic_only"))

    zones = model.get("trust_zones")
    zone_ids = [item.get("id") for item in zones or [] if isinstance(item, dict)]
    if set(zone_ids) != REQUIRED_ZONES or len(zone_ids) != len(REQUIRED_ZONES):
        errors.append(DfdError("DFD-ZONES", "trust_zones", "Z0 through Z6 must be declared exactly once"))

    classifications = model.get("classifications")
    class_ids = [item.get("id") for item in classifications or [] if isinstance(item, dict)]
    if set(class_ids) != REQUIRED_CLASSES or len(class_ids) != len(REQUIRED_CLASSES):
        errors.append(
            DfdError("DFD-CLASSIFICATIONS", "classifications", "canonical classifications must be exact")
        )
    ranks = [item.get("rank") for item in classifications or [] if isinstance(item, dict)]
    if set(ranks) != set(range(6)) or len(ranks) != 6:
        errors.append(DfdError("DFD-CLASS-RANK", "classifications", "classification ranks must be 0 through 5"))

    stores = model.get("stores")
    if not isinstance(stores, list) or set(stores) != REQUIRED_STORES or len(stores) != len(REQUIRED_STORES):
        errors.append(DfdError("DFD-STORES", "stores", "approved stores must be declared exactly once"))
    known_stores = set(stores) if isinstance(stores, list) else set()

    denylist = model.get("global_log_denylist")
    if not isinstance(denylist, list) or not REQUIRED_LOG_DENYLIST.issubset(set(denylist)):
        errors.append(DfdError("DFD-LOG-DENYLIST", "global_log_denylist", "required sensitive fields are missing"))
    denied_log_fields = set(denylist) if isinstance(denylist, list) else set()

    threat_ids = _catalog_ids(model, "threat_catalog", errors)
    control_ids = _catalog_ids(model, "control_catalog", errors)
    test_ids = _catalog_ids(model, "negative_test_catalog", errors)
    severities = {
        item.get("id"): item.get("severity")
        for item in model.get("threat_catalog", [])
        if isinstance(item, dict)
    }
    for threat_id, severity in severities.items():
        if severity not in {"low", "medium", "high", "critical"}:
            errors.append(DfdError("DFD-THREAT-SEVERITY", f"threat_catalog.{threat_id}", "severity is invalid"))

    flows = model.get("flows")
    if not isinstance(flows, list):
        return sorted(set(errors + [DfdError("DFD-FLOWS", "flows", "flows must be a list")]))
    flow_ids = [item.get("id") for item in flows if isinstance(item, dict)]
    if set(flow_ids) != REQUIRED_FLOWS or len(flow_ids) != len(REQUIRED_FLOWS):
        errors.append(DfdError("DFD-FLOW-SET", "flows", "F01 through F13 must be declared exactly once"))

    flow_map: dict[str, dict[str, Any]] = {}
    for flow in flows:
        if not isinstance(flow, dict) or not isinstance(flow.get("id"), str):
            errors.append(DfdError("DFD-FLOW-ID", "flows", "every flow requires a string id"))
            continue
        flow_id = flow["id"]
        flow_map[flow_id] = flow
        for field in (
            "name",
            "actor",
            "purpose",
            "protocol",
            "authentication",
            "encryption",
            "authoritative_effect",
            "degraded_mode",
            "owner_role",
        ):
            _require_text(flow, flow_id, field, errors)

        path = flow.get("path")
        if not isinstance(path, list) or len(path) < 2:
            errors.append(DfdError("DFD-FLOW-PATH", f"flows.{flow_id}.path", "at least two zones are required"))
            path = []
        for zone in path:
            if zone not in REQUIRED_ZONES:
                errors.append(DfdError("DFD-FLOW-ZONE", f"flows.{flow_id}.path", f"unknown zone {zone!r}"))
        if any(left == right for left, right in zip(path, path[1:])):
            errors.append(DfdError("DFD-FLOW-BOUNDARY", f"flows.{flow_id}.path", "adjacent zones must differ"))

        company_scope = flow.get("company_scope")
        if company_scope not in COMPANY_SCOPES:
            errors.append(DfdError("DFD-COMPANY-SCOPE", f"flows.{flow_id}", "company scope is unknown"))

        data_classes = flow.get("data_classes")
        if not isinstance(data_classes, list) or not data_classes:
            errors.append(DfdError("DFD-FLOW-CLASS", f"flows.{flow_id}.data_classes", "at least one class is required"))
            data_classes = []
        for classification in data_classes:
            if classification not in REQUIRED_CLASSES:
                errors.append(DfdError("DFD-FLOW-CLASS", f"flows.{flow_id}.data_classes", f"unknown class {classification!r}"))
        if "prohibited" in data_classes:
            errors.append(DfdError("DFD-PROHIBITED-DATA", f"flows.{flow_id}.data_classes", "prohibited data cannot enter a flow"))
        if "financial_sensitive" in data_classes and company_scope not in {"required_verified", "preserved_verified"}:
            errors.append(DfdError("DFD-FINANCIAL-SCOPE", f"flows.{flow_id}", "financial data requires a verified company scope"))

        persistence = flow.get("persistence")
        if not isinstance(persistence, list) or not persistence:
            errors.append(DfdError("DFD-PERSISTENCE", f"flows.{flow_id}.persistence", "persistence contract is required"))
            persistence = []
        for index, item in enumerate(persistence):
            location = f"flows.{flow_id}.persistence.{index}"
            if not isinstance(item, dict):
                errors.append(DfdError("DFD-PERSISTENCE-ITEM", location, "persistence item must be an object"))
                continue
            if item.get("store") not in known_stores:
                errors.append(DfdError("DFD-PERSISTENCE-STORE", location, "store is not approved"))
            for field in ("form", "retention_policy_id", "deletion_mode"):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    errors.append(DfdError("DFD-PERSISTENCE-FIELD", f"{location}.{field}", "non-empty value is required"))

        allowed_logs = flow.get("allowed_log_fields")
        if not isinstance(allowed_logs, list) or not allowed_logs:
            errors.append(DfdError("DFD-LOG-ALLOWLIST", f"flows.{flow_id}", "explicit log allowlist is required"))
            allowed_logs = []
        forbidden_allowed = set(allowed_logs) & denied_log_fields
        for field in sorted(forbidden_allowed):
            errors.append(DfdError("DFD-LOG-FIELD-FORBIDDEN", f"flows.{flow_id}.allowed_log_fields", f"{field} is globally denied"))

        egress = flow.get("egress")
        if not isinstance(egress, dict) or egress.get("mode") not in EGRESS_MODES:
            errors.append(DfdError("DFD-EGRESS", f"flows.{flow_id}.egress", "egress contract is invalid"))
            egress = {}
        mode = egress.get("mode")
        gateway = egress.get("gateway")
        if mode == "none" and gateway is not None:
            errors.append(DfdError("DFD-EGRESS-GATEWAY", f"flows.{flow_id}.egress", "none must not name a gateway"))
        if mode != "none" and (not isinstance(gateway, str) or not gateway):
            errors.append(DfdError("DFD-EGRESS-GATEWAY", f"flows.{flow_id}.egress", "non-none mode requires a gateway"))
        if mode == "approved_gateway" and "Z5" not in path:
            errors.append(DfdError("DFD-EGRESS-ZONE", f"flows.{flow_id}.path", "approved egress must cross Z5"))
        if mode == "external_ingress" and (not path or path[0] != "Z0"):
            errors.append(DfdError("DFD-INGRESS-ZONE", f"flows.{flow_id}.path", "external ingress must start in Z0"))
        if mode == "user_delivery" and (not path or path[-1] != "Z0"):
            errors.append(DfdError("DFD-DELIVERY-ZONE", f"flows.{flow_id}.path", "user delivery must end in Z0"))

        for key, known, minimum in (
            ("threats", threat_ids, 2),
            ("controls", control_ids, 2),
            ("negative_tests", test_ids, 1),
        ):
            values = flow.get(key)
            if not isinstance(values, list) or len(values) < minimum:
                errors.append(DfdError("DFD-FLOW-COVERAGE", f"flows.{flow_id}.{key}", f"at least {minimum} entries are required"))
                values = []
            for value in values:
                if value not in known:
                    errors.append(DfdError("DFD-FLOW-REFERENCE", f"flows.{flow_id}.{key}", f"unknown reference {value!r}"))
        flow_threats = set(flow.get("threats", []))
        if any(severities.get(threat) in {"high", "critical"} for threat in flow_threats) and not flow.get("negative_tests"):
            errors.append(DfdError("DFD-HIGH-THREAT-TEST", f"flows.{flow_id}", "high threats require a negative test"))
        if "financial_sensitive" in data_classes:
            _require_controls(flow, flow_id, {"C-COMPANY"}, errors)
        if "Z3" in path:
            _require_controls(flow, flow_id, {"C-WORKER"}, errors)

    special_controls = {
        "F02": {"C-QUAR"},
        "F03": {"C-SCAN", "C-WORKER", "C-MANIFEST"},
        "F04": {"C-WORKER", "C-MANIFEST"},
        "F05": {"C-COMPLETE", "C-LINEAGE"},
        "F06": {"C-SOD", "C-DECIMAL", "C-LINEAGE"},
        "F07": {"C-EXPORT", "C-REVOKE"},
        "F08": {"C-AI", "C-EGRESS"},
        "F09": {"C-SIGN", "C-IDEMP"},
        "F10": {"C-AUDIT", "C-LOG"},
        "F11": {"C-DELETE", "C-AUDIT"},
        "F12": {"C-RESTORE", "C-DELETE"},
        "F13": {"C-REVOKE", "C-AUDIT"},
    }
    for flow_id, required in special_controls.items():
        if flow_id in flow_map:
            _require_controls(flow_map[flow_id], flow_id, required, errors)

    if "F04" in flow_map:
        if flow_map["F04"].get("egress", {}).get("mode") != "none":
            errors.append(DfdError("DFD-WORKER-EGRESS", "flows.F04.egress", "parser worker must have no egress"))
        if flow_map["F04"].get("authoritative_effect") != "manifest_only_no_canonical_write":
            errors.append(DfdError("DFD-WORKER-AUTHORITY", "flows.F04", "worker may return only a manifest"))
    if "F08" in flow_map:
        ai_classes = set(flow_map["F08"].get("data_classes", []))
        if ai_classes & {"financial_sensitive", "secret", "prohibited"}:
            errors.append(DfdError("DFD-AI-CLASS", "flows.F08.data_classes", "AI flow is minimized below financial_sensitive"))
        effect = flow_map["F08"].get("authoritative_effect", "")
        if "no_money_access_match_or_close_authority" not in effect:
            errors.append(DfdError("DFD-AI-AUTHORITY", "flows.F08", "AI authority prohibition must be explicit"))
    if "F11" in flow_map:
        if not _has_store(flow_map["F11"], "security_archive"):
            errors.append(DfdError("DFD-DELETE-LEDGER", "flows.F11", "delete ledger must live in security archive"))
        forms = " ".join(item.get("form", "") for item in flow_map["F11"].get("persistence", []) if isinstance(item, dict))
        if "outside_ordinary_restore" not in forms:
            errors.append(DfdError("DFD-DELETE-RESTORE-SEPARATION", "flows.F11", "delete ledger must be outside ordinary restore"))
    if "F12" in flow_map and "closed" not in flow_map["F12"].get("degraded_mode", ""):
        errors.append(DfdError("DFD-RESTORE-FAIL-CLOSED", "flows.F12", "service must remain closed until reconciled"))
    if "F13" in flow_map:
        forms = " ".join(item.get("form", "") for item in flow_map["F13"].get("persistence", []) if isinstance(item, dict))
        if "authorization_version" not in forms:
            errors.append(DfdError("DFD-REVOCATION-VERSION", "flows.F13", "revocation must persist authorization_version"))

    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia executable DFD")
    parser.add_argument(
        "model",
        type=Path,
        nargs="?",
        default=Path("docs/architecture/dfd-flows.json"),
    )
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    errors = validate_model(model)
    print(json.dumps({"errors": [error.as_dict() for error in errors], "ok": not errors}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
