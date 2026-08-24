"""Validate proposed store/classification/release alignment (FNC-ARC-006A)."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

NEWLINE = chr(10)

REQUIRED_TOP_LEVEL = {
    "schema_version", "task_id", "status", "data_ceiling", "human_acceptance",
    "decision_states", "store_contract", "classification_contract",
    "engine_release_profile", "gates", "required_tests",
}
REQUIRED_TESTS = {
    "TST-XCON-001", "TST-XCON-002", "TST-XCON-003",
    "TST-XCON-004", "TST-XCON-005", "TST-XCON-006",
}
FLOATING_VERSIONS = {"latest", "main", "head", "stable", "current"}
REQUIRED_ADR_TOKENS = {
    "source_tree_clean", "dependency_lock_digest", "build_provenance_ref",
    "attestation_ref", "signature_ref", "builder_identity", "build_timestamp",
}


@dataclass(frozen=True, order=True)
class CrossContractError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _ids(items: list[Any]) -> set[str]:
    return {item["id"] if isinstance(item, dict) else item for item in items}


def validate_model(
    model: dict[str, Any],
    boundaries: dict[str, Any],
    dfd: dict[str, Any],
    canonical: dict[str, Any],
    lineage: dict[str, Any],
    adr_text: str,
    migrations: str = "",
) -> list[CrossContractError]:
    errors: list[CrossContractError] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append(CrossContractError(code, location, message))

    if set(model) != REQUIRED_TOP_LEVEL:
        fail("XCON-TOP-LEVEL", "$", "top-level keys must be exact")
    if model.get("schema_version") != 1 or model.get("task_id") != "FNC-ARC-006A":
        fail("XCON-HEADER", "$", "schema/task header is invalid")
    if model.get("status") != "review_pending" or model.get("human_acceptance") != "pending":
        fail("XCON-STATUS", "$", "agent work remains review_pending with human acceptance pending")
    if model.get("data_ceiling") != "synthetic_only":
        fail("XCON-DATA", "data_ceiling", "only synthetic data is allowed")
    decisions = model.get("decision_states", {})
    if decisions != {"DR-ARC-001": "proposed", "DR-PRV-001": "proposed"}:
        fail("XCON-DECISION", "decision_states", "both decisions stay proposed")

    store_contract = model.get("store_contract", {})
    mappings = store_contract.get("mappings", [])
    mapping_ids = [mapping.get("id") for mapping in mappings]
    if len(mapping_ids) != len(set(mapping_ids)):
        fail("XCON-STORE-ID", "store_contract.mappings", "mapping IDs must be unique")

    boundary_stores = _ids(boundaries.get("stores", []))
    dfd_stores = set(dfd.get("stores", []))
    mapped_boundary = [mapping.get("boundary_store_id") for mapping in mappings
                       if mapping.get("boundary_store_id") is not None]
    mapped_dfd = [item for mapping in mappings for item in mapping.get("dfd_store_ids", [])]
    if set(mapped_boundary) != boundary_stores or len(mapped_boundary) != len(set(mapped_boundary)):
        fail("XCON-BOUNDARY-COVERAGE", "store_contract.mappings",
             "every boundary store must be mapped exactly once")
    if set(mapped_dfd) != dfd_stores or len(mapped_dfd) != len(set(mapped_dfd)):
        fail("XCON-DFD-COVERAGE", "store_contract.mappings",
             "every DFD store must be mapped exactly once")

    persisted = {
        persistence.get("store")
        for flow in dfd.get("flows", [])
        for persistence in flow.get("persistence", [])
    }
    authority = {store["id"]: store.get("authority_scope")
                 for store in boundaries.get("stores", [])}
    for mapping in mappings:
        location = f"store_contract.mappings[{mapping.get('id')}]"
        dfd_ids = set(mapping.get("dfd_store_ids", []))
        active_members = dfd_ids & persisted
        expected_state = "active" if active_members else "capability_only"
        if active_members and active_members != dfd_ids:
            fail("XCON-STORE-PARTIAL", location, "one mapping cannot mix active and inactive stores")
        if mapping.get("usage_state") != expected_state:
            fail("XCON-STORE-USAGE", location,
                 f"usage_state must be {expected_state} from DFD persistence")
        if mapping.get("decision_state") not in {"proposed", "pending_human"}:
            fail("XCON-STORE-DECISION", location, "store decision cannot be agent-accepted")
        boundary_id = mapping.get("boundary_store_id")
        if boundary_id is None:
            if mapping.get("resolution_kind") != "boundary_addition_pending" or \
                    mapping.get("decision_state") != "pending_human":
                fail("XCON-STORE-UNRESOLVED", location,
                     "a DFD-only store needs an explicit pending boundary addition")
        elif mapping.get("usage_state") == "active" and authority.get(boundary_id) == "none":
            fail("XCON-STORE-AUTHORITY", location,
                 "a no-authority capability cannot persist authoritative state")
        if mapping.get("resolution_kind") == "physical_zones" and \
                mapping.get("zone_isolation_required") is not True:
            fail("XCON-ZONE-ISOLATION", location, "physical object zones stay isolated")
    if store_contract.get("inactive_store_persistence_effect") != "blocked":
        fail("XCON-INACTIVE-EFFECT", "store_contract", "inactive store persistence must block")

    classifications = model.get("classification_contract", {})
    shared = set(classifications.get("shared_domain_classes", []))
    edge_only = set(classifications.get("dfd_edge_only_classes", []))
    canonical_classes = set(canonical.get("classifications", []))
    dfd_by_id = {item["id"]: item for item in dfd.get("classifications", [])}
    dfd_classes = set(dfd_by_id)
    if shared != canonical_classes:
        fail("XCON-CLASS-CANONICAL", "classification_contract.shared_domain_classes",
             "shared classes must equal canonical classifications")
    if shared | edge_only != dfd_classes or edge_only != {"public", "prohibited"}:
        fail("XCON-CLASS-DFD", "classification_contract.dfd_edge_only_classes",
             "DFD must be shared classes plus public/prohibited")
    ranks = [dfd_by_id[item]["rank"] for item in
             ("public", "internal", "confidential", "financial_sensitive", "secret", "prohibited")]
    if ranks != list(range(6)):
        fail("XCON-CLASS-RANK", "dfd.classifications", "classification ranks must be monotonic")
    entity_classes = {entity.get("classification") for entity in canonical.get("entities", [])}
    if not entity_classes <= shared or classifications.get("public_canonical_entity_allowed") is not False \
            or classifications.get("prohibited_canonical_entity_allowed") is not False:
        fail("XCON-CLASS-ENTITY", "canonical.entities",
             "canonical entities use only shared persisted-domain classes")
    prohibited = dfd_by_id.get("prohibited", {})
    if classifications.get("prohibited_persistence") != "forbidden" or \
            classifications.get("prohibited_egress") != "forbidden" or \
            prohibited.get("persist") != "forbidden" or prohibited.get("egress") != "forbidden":
        fail("XCON-PROHIBITED", "classification_contract", "prohibited means no persistence or egress")
    if classifications.get("secret_persistence") != "vault_only" or \
            dfd_by_id.get("secret", {}).get("persist") != "vault_only":
        fail("XCON-SECRET", "classification_contract", "secret persists only in vault")
    personal = classifications.get("personal_data_axis", {})
    if personal != {
        "decision_request": "DR-PRV-001",
        "state": "pending_human",
        "orthogonal_to_operational_classification": True,
        "unknown_external_egress": "blocked_when_assessment_required",
        "agent_may_define_taxonomy": False,
    }:
        fail("XCON-PERSONAL-AXIS", "classification_contract.personal_data_axis",
             "personal-data taxonomy stays orthogonal, pending and fail-closed")

    profile = model.get("engine_release_profile", {})
    expected_release_fields = set(lineage.get("engine_release_contract", {}).get("required_fields", []))
    if set(profile.get("required_fields", [])) != expected_release_fields:
        fail("XCON-RELEASE-FIELDS", "engine_release_profile.required_fields",
             "release profile must exactly match DOM-005")
    if set(profile.get("floating_versions_forbidden", [])) != FLOATING_VERSIONS:
        fail("XCON-RELEASE-FLOATING", "engine_release_profile",
             "all floating versions must remain forbidden")
    if profile.get("agent_can_approve_release") is not False or \
            profile.get("unverifiable_release_effect") != "block_publication_and_close":
        fail("XCON-RELEASE-AUTHORITY", "engine_release_profile",
             "agent cannot approve and unverifiable release blocks")
    for token in sorted(REQUIRED_ADR_TOKENS):
        if token not in adr_text:
            fail("XCON-ADR-PROFILE", "ADR-023", f"ADR implementation profile misses {token}")

    # -- el contrato y el esquema hablan del mismo sistema -----------------
    # Cada contrato de linaje nombra sus tablas fisicas. Si el SQL no las crea,
    # el contrato describe algo que no existe, y eso no lo detecta ninguno de
    # los dos validadores por separado.
    declared: dict[str, str] = {}
    for key in ("transform_plan_contract", "row_override_contract"):
        section = lineage.get(key) or {}
        for table in section.get("physical_tables") or []:
            declared[str(table)] = f"lineage-model.{key}"
        if section.get("physical_table"):
            declared[str(section["physical_table"])] = f"lineage-model.{key}"
    approval = (lineage.get("engine_release_contract") or {}).get("approval_record") or {}
    if approval.get("physical_table"):
        declared[str(approval["physical_table"])] = (
            "lineage-model.engine_release_contract.approval_record")
    if not declared:
        fail("XCON-LINEAGE-TABLES", "lineage-model",
             "the lineage contracts name no physical table, so nothing ties them "
             "to the schema")
    for table, where in sorted(declared.items()):
        if f"CREATE TABLE {table}" not in migrations:
            fail("XCON-LINEAGE-TABLES", where,
                 f"{table} is declared but no migration creates it")

    if set(model.get("required_tests", [])) != REQUIRED_TESTS:
        fail("XCON-TESTS", "required_tests", "required cross-contract tests must be exact")
    for gate in model.get("gates", []):
        if gate.get("status") != "not_met" or gate.get("acceptance") != "pending_human":
            fail("XCON-GATE", f"gates[{gate.get('id')}]", "agent cannot meet a gate")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Fincilia cross-contract vocabulary")
    parser.add_argument("model", type=Path, nargs="?",
                        default=Path("docs/architecture/cross-contract-vocabulary.json"))
    parser.add_argument("--boundaries", type=Path,
                        default=Path("docs/architecture/module-boundaries.json"))
    parser.add_argument("--dfd", type=Path, default=Path("docs/architecture/dfd-flows.json"))
    parser.add_argument("--canonical", type=Path, default=Path("docs/domain/canonical-model.json"))
    parser.add_argument("--lineage", type=Path, default=Path("docs/domain/lineage-model.json"))
    parser.add_argument("--adr", type=Path, default=Path("docs/adr/ADR-023-engine-release.md"))
    parser.add_argument("--migrations", type=Path, default=Path("db/migrations"))
    args = parser.parse_args()
    # Lo que importa es como acaba el esquema, no en que fichero se dijo: las
    # migraciones se leen juntas.
    migrations = NEWLINE.join(item.read_text(encoding="utf-8")
                              for item in sorted(args.migrations.glob("*.sql")))
    errors = validate_model(
        json.loads(args.model.read_text(encoding="utf-8")),
        json.loads(args.boundaries.read_text(encoding="utf-8")),
        json.loads(args.dfd.read_text(encoding="utf-8")),
        json.loads(args.canonical.read_text(encoding="utf-8")),
        json.loads(args.lineage.read_text(encoding="utf-8")),
        args.adr.read_text(encoding="utf-8"),
        migrations,
    )
    print(json.dumps({"errors": [error.as_dict() for error in errors], "ok": not errors},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
