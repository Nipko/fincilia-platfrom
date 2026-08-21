from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REQUIRED_PLANES = {"control", "financial", "evidence", "analytics", "security"}
REQUIRED_MODULES = {
    "access",
    "ai_gateway",
    "analytics",
    "audit",
    "clean",
    "close",
    "finance",
    "ingestion",
    "platform",
    "reconciliation",
    "reporting",
    "risk",
    "sources",
    "tenancy",
    "usage",
}
REQUIRED_INVARIANTS = {
    "ARC-AI-NO-MONEY",
    "ARC-CACHE-NONAUTHORITATIVE",
    "ARC-COMPANY-STABLE",
    "ARC-EVIDENCE-LINEAGE",
    "ARC-NO-CROSS-WRITE",
    "ARC-WORKER-MANIFEST",
}
REQUIRED_STORES = {
    "postgresql": "domain_and_visible_workflow_state",
    "object_storage": "binary_evidence_versions",
    "temporal": "durable_execution_history",
    "valkey": "none",
    "analytics_store": "none",
    "security_archive": "audit_and_delete_ledger",
}
FINANCIAL_AUTHORITY_MODULES = {"finance", "reconciliation", "close"}


@dataclass(frozen=True, order=True)
class ModelError:
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


def _cycle_nodes(graph: dict[str, set[str]]) -> set[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    cycles: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in visiting:
            start = path.index(node)
            cycles.update(path[start:])
            return
        if node in visited:
            return
        visiting.add(node)
        path.append(node)
        for dependency in graph.get(node, set()):
            if dependency in graph:
                visit(dependency, path)
        path.pop()
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node, [])
    return cycles


def validate_model(model: dict[str, Any]) -> list[ModelError]:
    errors: list[ModelError] = []
    if model.get("schema_version") != 1:
        errors.append(ModelError("ARC-SCHEMA-VERSION", "$", "schema_version must equal 1"))

    planes = model.get("planes")
    if not isinstance(planes, list) or set(planes) != REQUIRED_PLANES:
        errors.append(ModelError("ARC-PLANES", "planes", "the five required planes must be declared exactly"))

    modules = model.get("modules")
    if not isinstance(modules, list):
        return errors + [ModelError("ARC-MODULES", "modules", "modules must be a list")]
    module_ids = [item.get("id") for item in modules if isinstance(item, dict)]
    if any(not isinstance(module_id, str) or not module_id for module_id in module_ids):
        errors.append(ModelError("ARC-MODULE-ID", "modules", "every module requires a non-empty id"))
    for duplicate in _duplicates([item for item in module_ids if isinstance(item, str)]):
        errors.append(ModelError("ARC-MODULE-DUPLICATE", f"modules.{duplicate}", "module id is duplicated"))
    known_modules = {item for item in module_ids if isinstance(item, str)}
    for missing in sorted(REQUIRED_MODULES - known_modules):
        errors.append(ModelError("ARC-MODULE-REQUIRED", f"modules.{missing}", "required module is missing"))

    entity_owner: dict[str, str] = {}
    graph: dict[str, set[str]] = {}
    for module in modules:
        if not isinstance(module, dict) or not isinstance(module.get("id"), str):
            continue
        module_id = module["id"]
        if module.get("plane") not in REQUIRED_PLANES:
            errors.append(ModelError("ARC-MODULE-PLANE", f"modules.{module_id}", "module plane is unknown"))
        owns = module.get("owns")
        if not isinstance(owns, list) or not owns:
            errors.append(ModelError("ARC-MODULE-OWNS", f"modules.{module_id}.owns", "owns must be non-empty"))
        else:
            for entity in owns:
                if not isinstance(entity, str) or not entity:
                    errors.append(ModelError("ARC-ENTITY-ID", f"modules.{module_id}.owns", "entity id is invalid"))
                    continue
                if entity in entity_owner:
                    errors.append(
                        ModelError(
                            "ARC-ENTITY-MULTIPLE-OWNERS",
                            f"modules.{module_id}.owns.{entity}",
                            f"entity is already owned by {entity_owner[entity]}",
                        )
                    )
                entity_owner[entity] = module_id
        dependencies = module.get("allowed_dependencies")
        if not isinstance(dependencies, list):
            errors.append(ModelError("ARC-DEPENDENCIES", f"modules.{module_id}", "allowed_dependencies must be a list"))
            dependencies = []
        graph[module_id] = set()
        for dependency in dependencies:
            if dependency == module_id:
                errors.append(ModelError("ARC-SELF-DEPENDENCY", f"modules.{module_id}", "self dependency is forbidden"))
            elif dependency not in known_modules:
                errors.append(
                    ModelError(
                        "ARC-DEPENDENCY-UNKNOWN",
                        f"modules.{module_id}.allowed_dependencies",
                        f"unknown module {dependency!r}",
                    )
                )
            else:
                graph[module_id].add(dependency)
        has_financial_authority = module.get("authoritative_financial_state") is True
        if has_financial_authority and module_id not in FINANCIAL_AUTHORITY_MODULES:
            errors.append(
                ModelError(
                    "ARC-FINANCIAL-AUTHORITY-FORBIDDEN",
                    f"modules.{module_id}",
                    "only finance, reconciliation and close may own authoritative financial state",
                )
            )
        if module_id in FINANCIAL_AUTHORITY_MODULES and not has_financial_authority:
            errors.append(
                ModelError(
                    "ARC-FINANCIAL-AUTHORITY-MISSING",
                    f"modules.{module_id}",
                    "financial module must declare authoritative state",
                )
            )

    for cycle_node in sorted(_cycle_nodes(graph)):
        errors.append(ModelError("ARC-DEPENDENCY-CYCLE", f"modules.{cycle_node}", "dependency cycle detected"))

    stores = model.get("stores")
    if not isinstance(stores, list):
        errors.append(ModelError("ARC-STORES", "stores", "stores must be a list"))
    else:
        store_map = {
            item.get("id"): item.get("authority_scope")
            for item in stores
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        for store_id, authority in REQUIRED_STORES.items():
            if store_map.get(store_id) != authority:
                errors.append(
                    ModelError(
                        "ARC-STORE-AUTHORITY",
                        f"stores.{store_id}",
                        f"authority_scope must equal {authority!r}",
                    )
                )

    invariants = model.get("global_invariants")
    invariant_ids = {
        item.get("id")
        for item in invariants or []
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for missing in sorted(REQUIRED_INVARIANTS - invariant_ids):
        errors.append(ModelError("ARC-INVARIANT-REQUIRED", f"global_invariants.{missing}", "invariant is missing"))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Fincilia executable architecture model")
    parser.add_argument(
        "model",
        type=Path,
        nargs="?",
        default=Path("docs/architecture/module-boundaries.json"),
    )
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    errors = validate_model(model)
    print(
        json.dumps(
            {"errors": [error.as_dict() for error in errors], "ok": not errors},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
