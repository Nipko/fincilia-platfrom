"""Plan de transformacion: las seis etapas logicas del linaje, por columna.

`lineage-model.json#required_paths` describe `PATH-FINANCIAL-FACT` como una
secuencia de seis etapas para **cada campo publicado**:

    artifact_version -> raw_locator -> extracted_field -> transformed_value
                     -> source_record_field -> financial_fact_field

El dato que hace viable cumplirlo: **las seis son propiedades de la columna, no
de la fila**. Leer la columna 3 como decimal con coma es exactamente la misma
decision en la fila 7 que en la 90.000. Guardarlas por fila no anadiria una sola
informacion nueva; anadiria cien mil copias de la misma.

Asi que el plan se construye una vez por `(version de mapeo, version del motor)`
y lo que varia por fila —la coordenada de la celda y la huella del valor— se
queda donde ya estaba: en `raw_record.origin_locator` y en
`canonical_movement.field_digests`.

Aqui no hay estado ni base de datos: el plan es una funcion del mapeo. Persistirlo
y reconstruirlo es cosa de la capa que tiene conexion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from .mapping import ColumnMapping
from .release import digest_of

# Las seis etapas, en el orden que declara el contrato. El indice en esta tupla
# **es** el `step_ordinal`, empezando en 1.
STAGES: Final[tuple[str, ...]] = (
    "artifact_version",
    "raw_locator",
    "extracted_field",
    "transformed_value",
    "source_record_field",
    "financial_fact_field",
)

# Que tipo semantico entra y sale de cada etapa, por campo canonico. La cadena de
# tipos es lo que hace la reconstruccion comprobable: si el tipo de salida de una
# etapa no es el de entrada de la siguiente, el plan esta mal construido.
FIELD_TYPES: Final[dict[str, str]] = {
    "occurred_on": "local_date",
    "description": "text",
    "reference": "text",
    "amount": "money_decimal",
    "direction": "enum:direction",
    "currency": "currency_code",
    "debit": "money_decimal",
    "credit": "money_decimal",
}

# Version del analizador y del conjunto de reglas que producen estas etapas. Suben
# cuando cambia como se lee algo, y entonces el plan es otro.
PARSER_VERSION: Final[str] = "csv-extractor-0.1.0"
RULE_VERSION: Final[str] = "column-mapping-0.1.0"


class LineageError(ValueError):
    """El plan no se puede construir o no reconstruye las seis etapas."""


@dataclass(frozen=True)
class TransformStep:
    """Una etapa logica de un campo, con todo lo que la hace auditable."""

    canonical_field: str
    step_ordinal: int
    stage: str
    operation: str
    input_semantic_type: str
    output_semantic_type: str
    transform_ref: str | None
    configuration_digest: str
    parser_version: str
    rule_version: str
    source_column: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "canonical_field": self.canonical_field,
            "step_ordinal": self.step_ordinal,
            "stage": self.stage,
            "operation": self.operation,
            "input_semantic_type": self.input_semantic_type,
            "output_semantic_type": self.output_semantic_type,
            "transform_ref": self.transform_ref,
            "configuration_digest": self.configuration_digest,
            "parser_version": self.parser_version,
            "rule_version": self.rule_version,
            "source_column": self.source_column,
        }


def _transform_of(field: str, mapping: ColumnMapping) -> str:
    """Como se convierte el texto de la celda en el valor tipado.

    Lleva el convenio dentro a proposito: `parse_date` sin mas no dice si el
    `02/03` de la fila era marzo o febrero, y esa es exactamente la pregunta que
    una discrepancia contable obliga a contestar.
    """
    if field == "occurred_on":
        return f"parse_date:{mapping.date_format}"
    if field in ("amount", "debit", "credit"):
        return f"normalise_amount:{mapping.decimal_format}"
    if field == "direction":
        return f"resolve_direction:{mapping.direction_mode}"
    if field == "currency":
        return f"declared_currency:{mapping.currency}"
    if field == "reference":
        return "normalise_reference"
    return "verbatim"


def build_plan(mapping: ColumnMapping, *, engine_release_key: str,
               delimiter: str = ",",
               decided_fields: frozenset[str] = frozenset()) -> tuple[TransformStep, ...]:
    """Las seis etapas de cada campo mapeado, en orden.

    `decided_fields` son los campos cuyo convenio resolvio una persona. Se marca
    en la referencia de la transformacion porque el camino tiene que poder decir
    que aqui hubo una decision, no una inferencia.
    """
    if not mapping.columns:
        raise LineageError("a mapping with no columns produces no lineage")

    steps: list[TransformStep] = []
    for field, column in sorted(mapping.columns.items()):
        final_type = FIELD_TYPES.get(field, "text")
        transform = _transform_of(field, mapping)
        if field in decided_fields:
            transform = f"{transform}#decided"
        configuration = digest_of({
            "column": int(column),
            "date_format": mapping.date_format,
            "decimal_format": mapping.decimal_format,
            "direction_mode": mapping.direction_mode,
            "currency": mapping.currency,
            "delimiter": delimiter,
            "engine_release_key": engine_release_key,
            "field": field,
        })

        # La cadena de tipos: bytes del artefacto, coordenada, texto de la celda,
        # valor tipado, y el mismo valor ya canonico y ya publicado.
        chain = (
            ("bytes", "artifact_reference", "included_in_snapshot",
             f"seal:{engine_release_key}"),
            ("artifact_reference", "cell_coordinate", "derived_from",
             f"locate:tabular_delimited:{delimiter}"),
            ("cell_coordinate", "cell_text", "derived_from",
             f"extract:csv:{delimiter}"),
            ("cell_text", final_type, "derived_from", transform),
            (final_type, final_type, "derived_from", f"canonicalise:{field}"),
            (final_type, final_type, "derived_from", f"publish:{field}"),
        )
        for ordinal, (incoming, outgoing, operation, reference) in enumerate(chain, 1):
            steps.append(TransformStep(
                canonical_field=field, step_ordinal=ordinal,
                stage=STAGES[ordinal - 1], operation=operation,
                input_semantic_type=incoming, output_semantic_type=outgoing,
                transform_ref=reference, configuration_digest=configuration,
                parser_version=PARSER_VERSION, rule_version=RULE_VERSION,
                source_column=int(column)))
    return tuple(steps)


def plan_digest(steps: tuple[TransformStep, ...]) -> str:
    """Huella del plan entero. Dos planes iguales tienen la misma."""
    return digest_of([step.as_dict() for step in steps])


def validate_plan(steps: tuple[TransformStep, ...],
                  fields: frozenset[str]) -> list[str]:
    """Motivos por los que este plan no reconstruye las seis etapas.

    Vacio significa que las reconstruye. Cualquier otra cosa **bloquea la
    publicacion**: el contrato dice `on_incomplete: block_publication` y
    `average_coverage_allowed: false`, asi que no hay cobertura parcial.
    """
    problems: list[str] = []
    by_field: dict[str, list[TransformStep]] = {}
    for step in steps:
        by_field.setdefault(step.canonical_field, []).append(step)

    for field in sorted(fields):
        chain = sorted(by_field.get(field, []), key=lambda item: item.step_ordinal)
        if len(chain) != len(STAGES):
            problems.append(
                f"{field}: {len(chain)} of {len(STAGES)} stages; a published field "
                "with a missing stage cannot be audited")
            continue
        if tuple(step.stage for step in chain) != STAGES:
            problems.append(f"{field}: stages out of contract order")
        for previous, following in zip(chain, chain[1:]):
            if previous.output_semantic_type != following.input_semantic_type:
                problems.append(
                    f"{field}: {previous.stage} emits {previous.output_semantic_type} "
                    f"and {following.stage} expects {following.input_semantic_type}")
        for step in chain:
            if step.operation in ("derived_from", "redacted_from") and not step.transform_ref:
                problems.append(f"{field}: {step.stage} claims the value flowed "
                                "without naming the transformation")

    extra = sorted(set(by_field) - set(fields))
    if extra:
        problems.append(f"the plan carries stages for unpublished fields: {extra}")
    return problems


def reconstruct(steps: tuple[TransformStep, ...], *, canonical_field: str,
                origin_locator: dict[str, Any], raw_record_id: str,
                source_record_id: str, movement_id: str,
                value_digest: str | None) -> list[dict[str, Any]]:
    """Las seis etapas de un campo concreto, con su identidad de fila.

    Es la reconstruccion: el plan pone **como**, la fila pone **cual**, y de la
    combinacion sale el camino completo. Si falta cualquiera de las dos, esto
    levanta en vez de devolver un camino a medias.
    """
    chain = sorted((step for step in steps if step.canonical_field == canonical_field),
                   key=lambda item: item.step_ordinal)
    if len(chain) != len(STAGES):
        raise LineageError(
            f"the plan has {len(chain)} of {len(STAGES)} stages for {canonical_field}")
    if not origin_locator:
        raise LineageError(f"no origin locator for {canonical_field}")

    column = chain[0].source_column
    cell = dict(origin_locator)
    if column is not None:
        cell["field_ordinal"] = int(column)

    # Que identifica cada etapa. No es decorativo: es lo que permite volver al
    # fichero, comprobar, y decir en que punto exacto un texto se volvio decimal.
    identity = {
        "artifact_version": {"artifact_sha256": origin_locator.get("artifact_sha256")},
        "raw_locator": {"raw_record_id": raw_record_id, "cell": cell},
        "extracted_field": {"raw_record_id": raw_record_id,
                            "field_ordinal": column},
        "transformed_value": {"raw_record_id": raw_record_id,
                              "canonical_field": canonical_field},
        "source_record_field": {"source_record_id": source_record_id,
                                "canonical_field": canonical_field},
        "financial_fact_field": {"movement_id": movement_id,
                                 "canonical_field": canonical_field,
                                 "value_digest": value_digest},
    }
    if value_digest is None:
        raise LineageError(
            f"no value digest for {canonical_field}; a published field without one "
            "cannot prove what was published")

    return [{**step.as_dict(), "identity": identity[step.stage]} for step in chain]
