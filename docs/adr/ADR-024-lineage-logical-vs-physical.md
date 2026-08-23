# ADR-024 — Representación lógica y física del linaje

- Status: Proposed
- Date: 2026-08-23
- Owners: Data + Architecture, UNASSIGNED
- Approvers: Security + QA, UNASSIGNED
- Gate: S1-READY
- Tasks: FNC-P3.5
- Plan refs: §18

## Context and decision drivers

`lineage-model.json#required_paths` declara `PATH-FINANCIAL-FACT` como una
secuencia de seis etapas para **cada campo publicado**, con
`coverage_requirement: 100_percent_of_published_fields` y
`average_coverage_allowed: false`:

```
artifact_version → raw_locator → extracted_field → transformed_value
                 → source_record_field → financial_fact_field
```

La primera implementación (FNC-P3) materializó dos nodos y dos aristas por campo
y por fila, y colapsó las tres etapas intermedias en una sola arista
`derived_from` con la transformación nombrada. Esa divergencia quedó declarada y
**no aceptada**.

Materializar las seis etapas con la misma estrategia hace el problema aritmético,
no filosófico. Un extracto de 200.000 líneas con cinco campos mapeados produce:

| Representación | Filas de grafo |
|---|---|
| seis etapas por campo y fila | 6.000.000 nodos + 5.000.000 aristas |
| lo implementado en P3 | 2.000.000 nodos + 2.000.000 aristas |
| lo que propone este ADR | 1 nodo + 1 arista + 30 pasos de plan |

El dato que cambia la conversación: **las seis etapas son propiedades de la
columna, no de la fila**. Leer la columna 3 como decimal con coma es exactamente
la misma decisión en la fila 7 que en la 90.000. Repetirla por fila no añade una
sola información nueva; añade cien mil copias de la misma.

Lo que sí varía por fila es la **coordenada** —qué celda— y el **valor** —qué
huella—. Y las dos ya viven en filas que existen: `raw_record.origin_locator` y,
desde `V0009`, `canonical_movement.field_digests`.

## Decision

Separar la representación **lógica** del linaje de su representación **física**.

**Lógica (no se rebaja nada).** Toda consulta de drill-down sobre un campo
publicado devuelve las seis etapas de `PATH-FINANCIAL-FACT`, en orden, cada una
con su operación tipada, su tipo semántico de entrada y de salida, su
transformación nombrada, sus versiones de parser y de regla, y su digest de
configuración. Si una sola etapa no se puede reconstruir, **la publicación se
bloquea**: no hay cobertura parcial ni promedio.

**Física.** Lo invariante por fila se guarda una vez y versionado; lo variable
por fila se guarda donde ya estaba.

| Qué | Dónde | Cardinalidad |
|---|---|---|
| las seis etapas, tipadas y versionadas | `lineage_transform_plan` + `lineage_transform_step` | 6 por campo y por **plan** |
| qué celda produjo el campo | `raw_record.origin_locator` + `lineage_transform_step.source_column` | ya existía |
| qué registro de origen | `source_record.raw_record_id` | ya existía |
| la huella del valor publicado | `canonical_movement.field_digests` | ya existía la fila |
| la evidencia terminal | `lineage_node(artifact_version)` + arista `included_in_snapshot` | 1 por dataset |

Un plan se ata a `(mapping_version_id, engine_release_id)` con `UNIQUE`. Cambiar
la transformación cambia el digest del mapeo o la versión del motor, luego es
otro par y otro plan. **El plan anterior no se toca**, así que un dataset
publicado hace seis meses sigue reconstruyendo sus seis etapas con las reglas de
entonces, que es justamente lo que `reprocessing_contract` exige.

Lo que **no** cambia respecto del contrato vigente:

- cobertura del 100% de campos publicados, sin promedios;
- localizador exacto: artefacto, sha256, fila, columna y tramo de bytes;
- versiones: motor, esquema canónico, parser y regla en cada etapa;
- `value_digest` por campo publicado, y **jamás el valor**;
- `derived_from`, `decided_using` e `included_in_snapshot` siguen siendo
  operaciones distintas y no intercambiables, ahora tipadas en el paso del plan;
- aristas append-only: una corrección agrega un plan, nunca reescribe uno.

## Alternatives rejected

**Materializar las seis etapas por fila.** Es la lectura literal del contrato y
la que menos hay que explicar. Se rechaza por aritmética: once millones de filas
de grafo por extracto convierten el linaje en la tabla más grande del sistema
para almacenar cien mil copias de cuatro decisiones. El coste no compra ninguna
capacidad de auditoría que la reconstrucción no dé.

**Dejar la divergencia de P3 como está.** Se rechaza porque pierde información
real: colapsar `extracted_field`, `transformed_value` y `source_record_field` en
una arista hace imposible contestar «¿en qué punto exacto se convirtió este texto
en un decimal?», que es la pregunta que una discrepancia contable obliga a hacer.

**Grafo materializado en un almacén aparte.** Se rechaza por alcance: mueve el
problema a un componente que hoy no existe, con su propia consistencia, sus
propios permisos y su propia copia de datos financieros.

**Calcular las etapas al vuelo sin plan persistido.** Se rechaza porque no es
reproducible: la reconstrucción dependería del código desplegado hoy, no de las
reglas con las que se publicó. Es exactamente el `latest` que
`reproducibility_manifest` prohíbe, con otro nombre.

## Consequences

### Positive

- El linaje deja de crecer con el producto de filas por campos.
- Cambiar una regla de lectura queda registrado como un plan nuevo, comparable
  paso a paso contra el anterior.
- La pregunta «¿por qué este importe es 1.234,56?» se contesta con la
  transformación nombrada de cada etapa, no con una sola arista genérica.

### Negative

- El drill-down deja de ser un `SELECT` sobre una tabla y pasa a ser una
  reconstrucción con reglas. Si esas reglas tienen un defecto, el defecto afecta
  a todas las respuestas a la vez, no a una fila.
- Hay dos sitios donde puede faltar una pieza —el plan y la fila— y el bloqueo de
  publicación tiene que comprobar los dos.
- Un lector que consulte las tablas directamente ya no ve el camino completo sin
  aplicar la reconstrucción.

## Security, privacy and data implications

El plan describe **cómo** se leyó, nunca **qué** se leyó: sus campos son tipos
semánticos, versiones y digests de configuración. `field_digests` guarda huellas
sha256, y la restricción `ck_movement_field_digests` acota su tamaño para que no
pueda usarse como almacén encubierto. La clasificación de datos personales no
cambia: el plan es metadato operativo y las coordenadas siguen en las tablas que
ya tienen RLS forzada.

## Migration and rollback

`V0009` añade el plan, sus pasos y `field_digests` sin tocar `V0001`–`V0008`.
Los datasets publicados antes del plan quedan marcados `lineage_state =
'invalidated'`: no pueden reconstruir seis etapas y decirlo es más honesto que
dejarlos marcados `complete`.

Volver atrás no exige revertir la migración: bastaría con reintroducir la
materialización por fila y dejar el plan como redundante. No hay pérdida de
información en ninguna dirección, porque el plan es un superconjunto de lo que la
arista colapsada decía.

## Verification evidence

- `docs/domain/lineage-model.json` — `required_paths`, `edge_operations`,
  `reprocessing_contract`.
- `docs/implementation/handoffs/FNC-P3.md` — la divergencia que este ADR resuelve.
- `db/migrations/V0009__onboarding_release_gate_and_lineage_plan.sql`.

## Review trigger

Se revisa si aparece cualquiera de estas tres cosas: una etapa lógica que no se
pueda reconstruir de forma determinista; un consumidor que necesite recorrer el
grafo sin pasar por la reconstrucción; o una regla de transformación que dependa
de la fila y no de la columna, que rompería la premisa entera de este ADR.

## References

- ADR-005 — Linaje por campo.
- ADR-023 — Engine release y reproducibilidad.
