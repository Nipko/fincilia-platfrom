---
task: FNC-DOM-005
status: REVIEW_PENDING
base_sha: a43bc1c
base_sha_verified: true
integration_base_sha: 5fb0220
integration_sha: see_git_commit_containing_this_handoff
implementer: Claude (external agent)
data_used: synthetic_only
human_acceptance: pending
quality_gate_on_git_index: passed
---

# Handoff FNC-DOM-005 — Linaje por campo, overlays y engine release reproducible

- **Estado:** `REVIEW_PENDING`
- **Agente:** Claude (external agent)
- **Accountable owner:** UNASSIGNED
- **Revisores requeridos:** Data, Accounting, Architecture, Security, Privacy
- **Base SHA declarada:** `a43bc1c`
- **Head SHA:** no disponible — ver §1
- **Rama/worktree:** no aplica; escritura directa sobre el árbol compartido, sin Git

Esta entrega **no declara S1-READY, DRG-00, producción lista, cumplimiento legal,
retención aceptada ni release aprobada**. No se usaron datos reales.

## 1. Base declarada y limitación de verificación

El agente externo no verificó Git por restricción de su encargo. El Integration Steward
verificó que `a43bc1c` existe y corresponde a `docs(privacy): route FNC-PRV-001 review
findings`. La integración se realizó sobre `5fb0220`; el commit final queda registrado por
la historia de Git porque un commit no puede contener autorreferencialmente su propio SHA.

Desviación de herramienta declarada: el encargo pedía `apply_patch`; esa herramienta no
existe en mi entorno. Usé escritura y edición directa de ficheros, sin Git y sin salir del
scope. El efecto sobre el árbol es el mismo; lo declaro para que la revisión no asuma un
mecanismo que no usé.

## 2. Objetivo y resultado

Convertir el seed de `LINEAGE_SPEC.md` en un contrato completo y ejecutable de
localizadores tipados, linaje por campo y decisión, overlays no destructivos,
`engine_release` inmutable y reprocesamiento versionado.

Resultado: contrato documentado, modelo JSON autoritativo, validador determinista con
**98 códigos de error únicos**, y **76 pruebas** que incluyen
los 20 escenarios obligatorios del encargo más el caso legítimo idéntico de DOM-004.

## 3. Paths modificados

| Ruta | Estado | Bytes |
|---|---|---:|
| `docs/domain/LINEAGE_SPEC.md` | ampliado sobre el seed, no sustituido | 15.955 |
| `docs/domain/lineage-model.json` | nuevo, autoritativo | 45.012 |
| `tools/lineage_model/__init__.py` | nuevo | 63 |
| `tools/lineage_model/validate.py` | nuevo | 39.468 |
| `tools/lineage_model/test_validate.py` | nuevo | 33.460 |
| `docs/implementation/handoffs/FNC-DOM-005.md` | nuevo, este documento | — |

Ninguna otra ruta fue creada, modificada ni leída en escritura. No se tocaron `AGENTS.md`,
`CURRENT_PHASE.md`, backlog, ownership, trazabilidad, gates, la ficha de tarea, CI,
workflows, Compose, lockfiles, archivos raíz, ADR, C4, DFD, threat model, privacy map,
`canonical-model.json`, `module-boundaries.json`, contratos DOM-002/003/004, apps, workers,
packages, SQL, migraciones ni fixtures.

**Paths reservados que se liberan:** los cuatro del encargo, más el handoff.

## 4. Cantidades del contrato

| Bloque | Cantidad |
|---|---:|
| Tipos de nodo | 10 (los 9 exigidos más `reference_data_value`) |
| Operaciones de arista | 6, con `derived_from` / `decided_using` / `included_in_snapshot` distintas |
| Campos obligatorios de arista | 21 |
| Caminos obligatorios | 5, todos con cobertura 100% y `average_coverage_allowed: false` |
| Familias de locator | 6 uniones discriminadas |
| Campos críticos con SoD | 8 |
| Estados de overlay | 7, con 10 transiciones |
| Campos del manifiesto de engine release | 22 |
| Campos del reproduction manifest | 20 |
| Entidades canónicas con `lineage_required` | 18, derivadas dinámicamente |
| Bindings de privacidad | 7 actividades PA, 6 políticas L-01 |
| Códigos de error únicos del validador | 98, incluidos vínculos DFD y threat model añadidos por integración |
| Pruebas | 76 |
| Decisiones abiertas declaradas | 5 |

## 5. Comandos ejecutados y resultado exacto

```powershell
python -m tools.lineage_model.validate
python -m unittest tools.lineage_model.test_validate -v
python -m unittest discover -s tools/lineage_model -p "test_*.py"
python -m tools.canonical_model.validate
python -m tools.idempotency_model.validate
```

| Comando | Resultado observado |
|---|---|
| `lineage_model.validate` | `{"errors": [], "ok": true}`, exit 0 |
| `unittest tools.lineage_model.test_validate` | `Ran 76 tests` · `OK` tras integración |
| `unittest discover -s tools/lineage_model` | `Ran 76 tests` · `OK` tras integración |
| `canonical_model.validate` | `{"errors": [], "ok": true}`, exit 0 — **sin regresión** |
| `idempotency_model.validate` | `{"errors": [], "ok": true}`, exit 0 — **sin regresión** |

Checks locales: JSON válido (28 claves de primer nivel); `LINEAGE_SPEC.md` con fences
balanceados y 11 secciones; cero merge markers; cero `TODO`/`FIXME` sin ID de tarea; cero
correos, NIT, cédulas, IP o URLs externas; las cinco rutas de código y documentación dentro
del scope autorizado.

### 5.1 Tests de mutación sobre el validador

correr pruebas en verde no demuestra por sí solo que el validador muerda. El agente externo
mutó ocho reglas críticas en una
copia fuera del repositorio y verifiqué que la suite las detecta. **Las ocho murieron:**

| Mutante | Regla eliminada | Pruebas que fallan |
|---|---|---:|
| M1 | detección de ciclos | 1 |
| M2 | rechazo de aristas cross-company | 1 |
| M3 | cobertura de camino completo hasta evidencia | 1 |
| M4 | conflicto por base stale en la cadena de overlays | 1 |
| M5 | bloqueo de overlays no aprobados | 1 |
| M6 | sincronía dinámica con `lineage_required` canónico | 1 |
| M7 | prohibición de tokens flotantes (`latest`) | 1 |
| M8 | cobertura SoD de campos financieros críticos | 1 |

## 6. Evidencia por escenario obligatorio

Los 20 escenarios del encargo están materializados con su ID como nombre de prueba, más
`TST-DED-002`:

`TST-LIN-001` a `TST-LIN-006` · `TST-OVR-001` a `TST-OVR-006` · `TST-PAR-001` a
`TST-PAR-007` · `TST-PRV-001` · `TST-DED-002`.

`TST-LIN-001` a `TST-LIN-004` se ejercitan contra un **grafo sintético real** mediante la
función pura `validate_graph`, no contra una afirmación del JSON. `TST-OVR-001` a
`TST-OVR-004` y `TST-OVR-006` se ejercitan contra `apply_overlay_chain`. `TST-PAR-001` se
ejercita contra `reproduction_key`.

## 7. Decisiones preservadas

Todas las del encargo se conservan y son verificadas por al menos una regla del validador:

- company como frontera financiera estable y nodos/aristas company-scoped;
- raw, artifact version, origin locator y cierres históricos inmutables;
- corregir crea overlay o versión; nunca edita evidencia de origen;
- camino completo hasta evidencia para todo campo publicado y decisión financiera;
- reprocess crea `dataset_version` sin reescribir registros, informes ni snapshots;
- engine release fija código y artefactos exactos;
- fecha, monto, referencia y fingerprint no son identidad dura;
- un LLM no calcula dinero, confirma match, autoriza acceso ni cierra;
- IA, OCR y modelos son productores versionados de propuesta o evidencia, no autoridad;
- `unknown`, linaje incompleto o release no verificable bloquean publicación y cierre;
- Valkey y analytics no son fuente de verdad;
- solo datos sintéticos, cero red y cero proveedores externos;
- **DR-PRV-001 permanece abierto**: el contrato define el mecanismo de propagación de los dos ejes y declara `resolved_here: false`; no inventa taxonomía legal.

## 8. Hallazgos fuera de scope

Cinco contradicciones entre contratos ya integrados. **No edité ninguna de sus rutas.**

1. **Dos vocabularios de store incompatibles.** `module-boundaries.json` declara seis stores (`object_storage`, `analytics_store`, …) y `dfd-flows.json` declara nueve, con el object storage partido en tres zonas y `vault` añadido. Solo en boundaries: `analytics_store`, `object_storage`. Solo en DFD: `analytics_projection`, `object_storage_quarantine`, `object_storage_raw`, `object_storage_derived`, `vault`. Un validador que cruce ambos no puede resolver referencias. **Owner: Architecture.** Es la misma familia que `DR-ARC-001`.

2. **Dos vocabularios de clasificación.** `canonical-model.json` declara cuatro clases; `dfd-flows.json` declara seis, añadiendo `public` y `prohibited`. Mi contrato apunta a la fuente canónica para `operational_classification`, pero la divergencia sigue abierta. **Owner: Architecture + Privacy**, relacionado con `DR-PRV-001`.

3. **`TEST_CATALOG.md` asigna `TST-PAR-001` a `FNC-QA-003`**, mientras ADR-023 y los criterios de aceptación de esta ficha lo asignan a FNC-DOM-005. Además el catálogo no contiene `TST-LIN-002`…`TST-LIN-006`, `TST-OVR-001`…`TST-OVR-006`, `TST-PAR-002`…`TST-PAR-007` ni `TST-PRV-001`, que esta entrega materializa. **Owner: QA + Integration Steward.**

4. **ADR-023 enumera menos campos de release de los que exige esta tarea.** El ADR fija semver, commit, SHA-256 del artefacto, SBOM, versión de esquema canónico y clasificación. El encargo añade `source_tree_clean`, `dependency_lock_digest`, `build_provenance_ref`, `attestation_ref`, `signature_ref`, `builder_identity` y `build_timestamp`. Implementé el superconjunto, que es el más estricto, pero **el ADR queda por detrás del contrato** y debería enmendarse para que no parezca que el contrato excede su decisión. **Owner: Architecture + Platform.**

5. **`reference_dataset_version` tiene `lineage_required: true` y `company_scoped: false`.** Es coherente —un dato de referencia se cita, no se copia por empresa— pero convierte «todo nodo con linaje es company-scoped» en una regla con excepción. Lo modelé como `reference_data_value`, un décimo tipo de nodo explícitamente no company-scoped. **Requiere confirmación de Data y Accounting** de que la excepción es la intención y no un descuido del modelo canónico.

## 9. Riesgos

1. **El contrato describe intención, no implementación.** No existe almacenamiento, ni grafo persistido, ni motor de overlays, ni pipeline de release. El validador comprueba que el **contrato** sea coherente, no que el sistema lo cumpla.
2. **Coste de almacenamiento del linaje por campo sin dimensionar.** Un camino completo por cada campo publicado multiplica filas y aristas. `UD-LOCATOR-STORAGE` queda abierto: si la representación física resulta inviable, la regla de cobertura 100% se vuelve una promesa que el sistema no podrá sostener.
3. **Proveedores externos sin versión fijable.** El contrato prohíbe prometer reproducibilidad en ese caso, pero no dice qué se ofrece en su lugar. `UD-EXTERNAL-MODEL-PINNING`.
4. **La aprobación de releases no tiene owner nominal.** `UD-RELEASE-APPROVAL`: el contrato exige un humano de Platform, pero Platform sigue `UNASSIGNED` en ownership.
5. **El eje personal está vacío por diseño.** Hasta que `DR-PRV-001` se cierre, todo nodo arrastra `unknown` y el bloqueo de egreso externo será la norma, no la excepción. Es correcto, pero conviene que Privacy sepa que el efecto práctico es «nada sale» hasta decidir.
6. **`issued_authorization_context` ya tiene evidencia ejecutable** en FNC-PLT-005 (`5fb0220`): company, principal, purpose, versión, emisión, expiración y revocación se revalidan en PostgreSQL. Sigue pendiente convertir el bootstrap del spike en migración productiva y auditar la emisión real.

## 10. Revisiones requeridas

| Rol | Qué debe revisar |
|---|---|
| **Data** | Tipos de nodo, las seis familias de locator, bases ordinales y validaciones de rango; el hallazgo 5; el coste de la cobertura 100%. |
| **Accounting** | Los ocho campos críticos con SoD; que `posting_date`, `value_date` y `accounting_date` se traten por separado; que el snapshot conserve release y version set; que el linaje no colapse dos hechos legítimos idénticos. |
| **Architecture** | Hallazgos 1, 2 y 4; ownership de `engine_release` en `platform`; la distinción `derived_from` / `decided_using` / `included_in_snapshot`; `UD-LOCATOR-STORAGE`. |
| **Security** | Ausencia de valores raw en nodos, aristas y logs; concurrencia optimista y ausencia de orden por reloj; imposibilidad de autoaprobar una release; que una release revocada no ejecute runs nuevos. |
| **Privacy** | Propagación de los dos ejes; que el contrato no resuelva `DR-PRV-001`; bloqueo de egreso con estado `unknown`; que el linaje no sea excusa para conservar payload personal suprimido. |

## 11. Compatibilidad y consumidores

Añade un módulo nuevo (`tools/lineage_model`) y un contrato nuevo
(`docs/domain/lineage-model.json`). No cambia esquemas, eventos, contratos compartidos ni
interfaces existentes. Los validadores canónico e idempotencia se ejecutaron después del
cambio y siguen en verde. No hay migraciones, eventos ni feature flags.

## 12. Rollback

Eliminar `docs/domain/lineage-model.json`, `tools/lineage_model/` y
`docs/implementation/handoffs/FNC-DOM-005.md`, y restaurar `docs/domain/LINEAGE_SPEC.md` a
su versión seed de 778 bytes. No hay esquema, migración, lockfile, CI ni configuración
compartida que revertir.

## 13. Fallos conocidos

Ninguno en la suite. Las limitaciones conocidas son las cinco decisiones abiertas de §14 y
los seis riesgos de §9, todas declaradas en el modelo.

## 14. Trabajo pendiente con IDs

| ID | Pregunta | Owner | Bloquea |
|---|---|---|---|
| `UD-DR-PRV-001` | Taxonomía del eje de dato personal y su obligatoriedad legal | Privacy | S1-READY, DRG-00 |
| `UD-DR-LEG-001` | Reloj y orden de retención de linaje frente a backups y tombstones | Legal | DRG-00 |
| `UD-RELEASE-APPROVAL` | Quién firma una release `approved` y con qué evidencia | Platform | S1-READY |
| `UD-LOCATOR-STORAGE` | Representación física y coste del linaje por campo | Architecture | S1-READY |
| `UD-EXTERNAL-MODEL-PINNING` | Qué ofrecer cuando un proveedor externo no fija versión | Architecture | DRG-01 |

## 15. Instrucciones para el Integration Steward

1. **Indexar** las cinco rutas de §3 más este handoff.
2. **Completado:** el Integration Steward ejecutó `python -m tools.quality_gate.cli` sobre las rutas indexadas; resultado PASS sin hallazgos.
3. **Integrar en CI** `python -m tools.lineage_model.validate` y `python -m unittest tools.lineage_model.test_validate`, junto a los validadores hermanos ya integrados.
4. **Completar** `integration_sha` en el frontmatter de este handoff y en la ficha `docs/implementation/tasks/FNC-DOM-005.md`, que yo no modifico.
5. **Actualizar** `CURRENT_PHASE.md`, backlog y trazabilidad: `FNC-DOM-005` pasa a *Review pending*, rutas `docs/domain/LINEAGE_SPEC.md`, `docs/domain/lineage-model.json`, `tools/lineage_model`, handoff.
6. **Actualizar `TEST_CATALOG.md`** con los 20 IDs materializados y **corregir la asignación de `TST-PAR-001`**, hoy atribuida a `FNC-QA-003` (hallazgo 3 de §8).
7. **Enrutar los hallazgos de §8**: 1 y 2 hacia `DR-ARC-001` y `DR-PRV-001`; 3 a QA; 4 a Architecture + Platform como enmienda de ADR-023; 5 a Data + Accounting.
8. **Añadir «Contrato de linaje, overlays y engine release» al checklist de salida de S1-READY sin marcarlo**: requiere firma de Data, Accounting, Architecture, Security y Privacy.
9. **No promover** ninguna decisión del modelo a `approved`, ningún gate a `met` ni ninguna release a `approved`. El validador lo rechazará, y esa es la intención.
