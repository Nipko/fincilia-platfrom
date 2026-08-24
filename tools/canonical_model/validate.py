from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# La lista es exacta a proposito: anadir una entidad al modelo financiero tiene
# que costar editar esto, y editarlo tiene que costar justificarlo. Lo que
# **no** entra aqui son las tablas cuya autoridad es otro contrato —el plan de
# linaje, la firma de una release, el punto de control de un lote—, por comodo
# que resulte tenerlas todas en el mismo sitio.
REQUIRED_ENTITIES = {
    "data_source", "data_source_account", "source_cycle", "source_expectation",
    "reference_dataset_version",
    "source_artifact", "artifact_version", "document", "processing_run",
    "raw_record", "dataset_version", "source_record",
    "counterparty", "financial_account", "obligation", "money_movement",
    "movement_evidence_link", "settlement", "ledger_entry", "ledger_line",
    "account_balance", "external_reference",
}

# Y lo que tiene prohibido entrar, con el contrato al que pertenece cada una.
# Sin esto, «anadirla al modelo canonico» seria siempre el camino corto.
FOREIGN_AUTHORITY = {
    "lineage_transform_plan": "lineage-model.json#transform_plan_contract",
    "lineage_transform_step": "lineage-model.json#transform_plan_contract",
    "lineage_row_override": "lineage-model.json#row_override_contract",
    "release_approval": "lineage-model.json#engine_release_contract",
    "dataset_chunk": "events-retries.json#checkpoint_contract",
}
REQUIRED_TYPES = {
    "uuid", "uuid_v7", "text", "boolean", "integer", "money_decimal",
    "currency_code", "instant", "local_date", "sha256", "json_document",
    "object_reference", "tokenized_identifier", "enum",
}
REQUIRED_INVARIANTS = {
    "DOM-COMPANY-NOT-NULL", "DOM-COMPOSITE-FK", "DOM-MONEY-DECIMAL",
    "DOM-DATE-SEMANTICS", "DOM-SOURCE-NOT-MOVEMENT", "DOM-EVIDENCE-LINK",
    "DOM-SAFE-DEDUPE", "DOM-BINARY-OBJECT-STORE", "DOM-JSON-BOUNDED",
    "DOM-LINEAGE-REQUIRED", "DOM-NO-COMPANY-CASCADE", "DOM-TOKENIZED-ACCOUNT",
}
CLASSIFICATIONS = {"internal", "confidential", "financial_sensitive", "secret"}
MUTATION_POLICIES = {
    "immutable_version", "append_only", "controlled_state_machine", "mutable_master_versioned"
}
RISKY_UNIQUE_FIELDS = {
    "amount", "gross_amount", "net_amount", "occurred_at", "posted_at",
    "value_date", "accounting_date", "direction", "external_reference",
    "normalized_value", "dedupe_fingerprint", "counterparty_id",
}
CORE_VERSIONED_FACTS = {
    "source_record", "obligation", "money_movement", "movement_evidence_link",
    "settlement", "ledger_entry", "ledger_line", "account_balance", "external_reference",
}


@dataclass(frozen=True, order=True)
class CanonicalModelError:
    code: str
    location: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _ids(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.get("id") for item in items if isinstance(item, dict) and isinstance(item.get("id"), str)]


def _duplicates(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _field_map(entity: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        field["name"]: field
        for field in entity.get("fields", [])
        if isinstance(field, dict) and isinstance(field.get("name"), str)
    }


def _require_fields(entity: dict[str, Any], required: set[str], errors: list[CanonicalModelError]) -> None:
    entity_id = entity.get("id", "unknown")
    present = set(_field_map(entity))
    for field in sorted(required - present):
        errors.append(CanonicalModelError("DOM-REQUIRED-FIELD", f"entities.{entity_id}.fields", f"{field} is required"))


def validate_model(model: dict[str, Any], architecture: dict[str, Any]) -> list[CanonicalModelError]:
    errors: list[CanonicalModelError] = []
    if model.get("schema_version") != 1:
        errors.append(CanonicalModelError("DOM-SCHEMA-VERSION", "$", "schema_version must equal 1"))
    if model.get("task_id") != "FNC-DOM-002":
        errors.append(CanonicalModelError("DOM-TASK", "task_id", "task_id must be FNC-DOM-002"))
    if model.get("status") != "review_pending":
        errors.append(CanonicalModelError("DOM-STATUS", "status", "model must remain review_pending"))
    if model.get("data_ceiling") != "synthetic_only":
        errors.append(CanonicalModelError("DOM-DATA-CEILING", "data_ceiling", "E0 permits synthetic_only"))

    type_ids = _ids(model.get("logical_types"))
    if set(type_ids) != REQUIRED_TYPES or len(type_ids) != len(REQUIRED_TYPES):
        errors.append(CanonicalModelError("DOM-TYPES", "logical_types", "required logical types must be exact"))
    money_type = next((item for item in model.get("logical_types", []) if item.get("id") == "money_decimal"), {})
    if money_type.get("storage") != "numeric" or money_type.get("float_forbidden") is not True:
        errors.append(CanonicalModelError("DOM-MONEY-TYPE", "logical_types.money_decimal", "money must use numeric and forbid float"))
    if money_type.get("json_representation") != "string":
        errors.append(CanonicalModelError("DOM-MONEY-JSON", "logical_types.money_decimal", "money JSON representation must be string"))

    classifications = model.get("classifications")
    if not isinstance(classifications, list) or set(classifications) != CLASSIFICATIONS:
        errors.append(CanonicalModelError("DOM-CLASSIFICATIONS", "classifications", "canonical classes must be exact and exclude prohibited"))
    enums = model.get("enums")
    known_enums = set(enums) if isinstance(enums, dict) else set()

    invariant_ids = set(_ids(model.get("global_invariants")))
    for missing in sorted(REQUIRED_INVARIANTS - invariant_ids):
        errors.append(CanonicalModelError("DOM-INVARIANT", f"global_invariants.{missing}", "required invariant is missing"))

    architecture_owners: dict[str, tuple[str, str, bool]] = {}
    for module in architecture.get("modules", []):
        if not isinstance(module, dict):
            continue
        for entity_id in module.get("owns", []):
            architecture_owners[entity_id] = (
                module.get("id"), module.get("plane"), module.get("authoritative_financial_state") is True
            )

    entities = model.get("entities")
    if not isinstance(entities, list):
        return sorted(set(errors + [CanonicalModelError("DOM-ENTITIES", "entities", "entities must be a list")]))
    entity_ids = _ids(entities)
    smuggled = sorted(set(entity_ids) & set(FOREIGN_AUTHORITY))
    for identifier in smuggled:
        errors.append(CanonicalModelError(
            "DOM-FOREIGN-AUTHORITY", f"entities.{identifier}",
            f"this belongs to {FOREIGN_AUTHORITY[identifier]}, not to the "
            "canonical financial model"))
    if set(entity_ids) != REQUIRED_ENTITIES or len(entity_ids) != len(REQUIRED_ENTITIES):
        errors.append(CanonicalModelError("DOM-ENTITY-SET", "entities", "required entities must be declared exactly once"))
    for duplicate in _duplicates(entity_ids):
        errors.append(CanonicalModelError("DOM-ENTITY-DUPLICATE", f"entities.{duplicate}", "entity id is duplicated"))
    entity_map = {entity.get("id"): entity for entity in entities if isinstance(entity, dict)}

    for entity in entities:
        if not isinstance(entity, dict) or not isinstance(entity.get("id"), str):
            errors.append(CanonicalModelError("DOM-ENTITY-ID", "entities", "every entity requires a string id"))
            continue
        entity_id = entity["id"]
        location = f"entities.{entity_id}"
        owner = architecture_owners.get(entity_id)
        if owner is None:
            errors.append(CanonicalModelError("DOM-OWNER-MISSING", location, "entity is absent from module ownership model"))
        else:
            if entity.get("owner_module") != owner[0] or entity.get("plane") != owner[1]:
                errors.append(CanonicalModelError("DOM-OWNER-MISMATCH", location, "owner module or plane differs from architecture"))
            if entity.get("authoritative_financial_state") is not owner[2]:
                errors.append(CanonicalModelError("DOM-AUTHORITY-MISMATCH", location, "financial authority differs from module"))
        if entity.get("classification") not in CLASSIFICATIONS:
            errors.append(CanonicalModelError("DOM-ENTITY-CLASS", location, "classification is unknown or prohibited"))
        if entity.get("mutation_policy") not in MUTATION_POLICIES:
            errors.append(CanonicalModelError("DOM-MUTATION-POLICY", location, "mutation policy is invalid"))
        if entity.get("owner_module") == "finance":
            if entity.get("company_scoped") is not True or entity.get("authoritative_financial_state") is not True:
                errors.append(CanonicalModelError("DOM-FINANCE-SCOPE", location, "finance entities must be company-scoped and authoritative"))
            if entity.get("lineage_required") is not True:
                errors.append(CanonicalModelError("DOM-FINANCE-LINEAGE", location, "finance entities require lineage"))

        fields = entity.get("fields")
        if not isinstance(fields, list) or not fields:
            errors.append(CanonicalModelError("DOM-FIELDS", f"{location}.fields", "fields must be non-empty"))
            fields = []
        field_names = [field.get("name") for field in fields if isinstance(field, dict) and isinstance(field.get("name"), str)]
        for duplicate in _duplicates(field_names):
            errors.append(CanonicalModelError("DOM-FIELD-DUPLICATE", f"{location}.fields.{duplicate}", "field is duplicated"))
        field_map = _field_map(entity)
        _require_fields(entity, {"id", "created_at"}, errors)
        id_field = field_map.get("id", {})
        if id_field.get("type") != "uuid_v7" or id_field.get("nullable") is not False or id_field.get("immutable") is not True:
            errors.append(CanonicalModelError("DOM-ID-CONTRACT", f"{location}.fields.id", "id must be immutable non-null uuid_v7"))
        if entity.get("company_scoped") is True:
            company = field_map.get("company_id", {})
            if company.get("type") != "uuid" or company.get("nullable") is not False or company.get("immutable") is not True:
                errors.append(CanonicalModelError("DOM-COMPANY-FIELD", f"{location}.fields.company_id", "company_id must be immutable non-null uuid"))
            identity_constraints = [
                constraint for constraint in entity.get("unique_constraints", [])
                if constraint.get("kind") == "entity_identity"
            ]
            if not any(constraint.get("fields") == ["company_id", "id"] for constraint in identity_constraints):
                errors.append(CanonicalModelError("DOM-COMPANY-IDENTITY", f"{location}.unique_constraints", "company entity identity must be company_id + id"))
        for field in fields:
            if not isinstance(field, dict):
                errors.append(CanonicalModelError("DOM-FIELD", f"{location}.fields", "field must be an object"))
                continue
            field_name = field.get("name", "unknown")
            field_type = field.get("type")
            if field_type not in REQUIRED_TYPES:
                errors.append(CanonicalModelError("DOM-FIELD-TYPE", f"{location}.fields.{field_name}", "logical type is unknown"))
            if not isinstance(field.get("nullable"), bool) or not isinstance(field.get("immutable"), bool):
                errors.append(CanonicalModelError("DOM-FIELD-FLAGS", f"{location}.fields.{field_name}", "nullable and immutable booleans are required"))
            if field_type == "enum" and field.get("enum_ref") not in known_enums:
                errors.append(CanonicalModelError("DOM-ENUM-REF", f"{location}.fields.{field_name}", "enum_ref is unknown"))
            if field_type == "json_document":
                if not isinstance(field.get("schema_ref"), str) or not isinstance(field.get("max_bytes"), int) or field.get("max_bytes", 0) <= 0:
                    errors.append(CanonicalModelError("DOM-JSON-CONTRACT", f"{location}.fields.{field_name}", "JSON requires schema_ref and positive max_bytes"))
            if field_type == "money_decimal" and not isinstance(field.get("value_rule"), str):
                errors.append(CanonicalModelError("DOM-MONEY-RULE", f"{location}.fields.{field_name}", "money field requires value_rule"))

        relationships = entity.get("relationships")
        if not isinstance(relationships, list):
            errors.append(CanonicalModelError("DOM-RELATIONSHIPS", f"{location}.relationships", "relationships must be a list"))
            relationships = []
        for relation in relationships:
            if not isinstance(relation, dict):
                errors.append(CanonicalModelError("DOM-RELATIONSHIP", f"{location}.relationships", "relationship must be an object"))
                continue
            target = entity_map.get(relation.get("target"))
            if target is None:
                errors.append(CanonicalModelError("DOM-RELATIONSHIP-TARGET", f"{location}.relationships", "target entity is unknown"))
                continue
            if relation.get("field") not in field_map:
                errors.append(CanonicalModelError("DOM-RELATIONSHIP-FIELD", f"{location}.relationships", "relationship field is missing"))
            if target.get("company_scoped") is True and entity.get("company_scoped") is True and relation.get("company_scoped_fk") is not True:
                errors.append(CanonicalModelError("DOM-COMPOSITE-FK", f"{location}.relationships.{relation.get('field')}", "company-scoped relationship must carry company_id"))
            if relation.get("on_delete") == "cascade":
                errors.append(CanonicalModelError("DOM-DELETE-CASCADE", f"{location}.relationships.{relation.get('field')}", "cascade is forbidden across canonical evidence/finance"))

        constraints = entity.get("unique_constraints")
        if not isinstance(constraints, list) or not constraints:
            errors.append(CanonicalModelError("DOM-UNIQUE-CONSTRAINTS", f"{location}.unique_constraints", "explicit identity constraint is required"))
            constraints = []
        for constraint in constraints:
            values = constraint.get("fields", []) if isinstance(constraint, dict) else []
            if any(field not in field_map for field in values):
                errors.append(CanonicalModelError("DOM-UNIQUE-FIELD", f"{location}.unique_constraints", "constraint references missing field"))
            if set(values) & RISKY_UNIQUE_FIELDS:
                errors.append(CanonicalModelError("DOM-UNSAFE-UNIQUE", f"{location}.unique_constraints.{constraint.get('id')}", "candidate financial fields cannot be hard unique"))

    for entity_id in CORE_VERSIONED_FACTS:
        entity = entity_map.get(entity_id)
        if entity:
            _require_fields(entity, {"engine_release_id", "canonical_schema_version", "lineage_state"}, errors)

    movement = entity_map.get("money_movement")
    if movement:
        _require_fields(movement, {"amount", "currency_code", "direction", "occurred_at", "posted_at", "value_date", "accounting_date", "dedupe_fingerprint"}, errors)
        fingerprint = _field_map(movement).get("dedupe_fingerprint", {})
        if fingerprint.get("value_rule") != "candidate_only_never_unique":
            errors.append(CanonicalModelError("DOM-DEDUPE-FINGERPRINT", "entities.money_movement.fields.dedupe_fingerprint", "fingerprint must remain candidate-only"))
    evidence_link = entity_map.get("movement_evidence_link")
    if evidence_link:
        targets = {item.get("target") for item in evidence_link.get("relationships", [])}
        if targets != {"money_movement", "source_record"}:
            errors.append(CanonicalModelError("DOM-EVIDENCE-LINK-TARGETS", "entities.movement_evidence_link", "link must connect movement and source record"))
    source_record = entity_map.get("source_record")
    if source_record and source_record.get("authoritative_financial_state") is not False:
        errors.append(CanonicalModelError("DOM-SOURCE-AUTHORITY", "entities.source_record", "source record is evidence, not authoritative finance"))
    settlement = entity_map.get("settlement")
    if settlement:
        _require_fields(settlement, {"gross_amount", "fee_amount", "tax_amount", "withholding_amount", "refund_amount", "adjustment_amount", "net_amount", "currency_code"}, errors)
    ledger_line = entity_map.get("ledger_line")
    if ledger_line:
        _require_fields(ledger_line, {"amount", "currency_code", "debit_credit"}, errors)
    account = entity_map.get("financial_account")
    if account:
        identifier = _field_map(account).get("identifier_token", {})
        if identifier.get("type") != "tokenized_identifier":
            errors.append(CanonicalModelError("DOM-ACCOUNT-TOKEN", "entities.financial_account.fields.identifier_token", "account identifier must be tokenized"))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Fincilia canonical model")
    parser.add_argument("model", type=Path, nargs="?", default=Path("docs/domain/canonical-model.json"))
    parser.add_argument("--architecture", type=Path, default=Path("docs/architecture/module-boundaries.json"))
    args = parser.parse_args()
    model = json.loads(args.model.read_text(encoding="utf-8"))
    architecture = json.loads(args.architecture.read_text(encoding="utf-8"))
    errors = validate_model(model, architecture)
    print(json.dumps({"errors": [error.as_dict() for error in errors], "ok": not errors}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
