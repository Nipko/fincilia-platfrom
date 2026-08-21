---
task: FNC-PRV-001
status: REVIEW_PENDING
base_sha: 00d9408
integration_sha: pending_integration_steward
implementer: Claude + Integration Steward
data_used: synthetic_only
human_acceptance: pending
quality_gate_on_git_index: passed_0_findings
---

# Handoff FNC-PRV-001 — Mapa de privacidad, tratamiento, retención y borrado

**Estado: `REVIEW_PENDING`.** Esta entrega **no supera S1-READY ni DRG-00**. No acepta
decisiones legales, riesgos residuales, regiones, proveedores ni gates en nombre de
propietarios humanos. Privacy y Legal son owners; Security, Architecture y Product deben
revisar antes de cualquier avance.

## 1. Archivos creados

| Ruta | Contenido |
|---|---|
| `docs/privacy/README.md` | Índice, comandos y límites explícitos de la entrega. |
| `docs/privacy/PRIVACY_MAP.md` | Documento de 18 secciones: estado, principios, roles, sujetos, inventario, finalidades, stores, retención, borrado, portabilidad, derechos, región, IA, cliente, incidentes, DPIA, gates y verificación. |
| `docs/privacy/privacy-map.json` | Modelo ejecutable y autoritativo. 22 claves de primer nivel. |
| `tools/privacy_model/__init__.py` | Paquete. |
| `tools/privacy_model/validate.py` | Validador determinista, solo biblioteca estándar. |
| `tools/privacy_model/test_validate.py` | 53 pruebas: 43 originales y 10 de endurecimiento de integración. |
| `docs/implementation/tasks/FNC-PRV-001.md` | Ficha de tarea. |
| `docs/implementation/handoffs/FNC-PRV-001.md` | Este documento. |

Ninguna otra ruta fue creada o modificada. No se tocaron `AGENTS.md`, `CURRENT_PHASE.md`,
backlogs, ownership, CI, Compose, ADR, `docs/domain/**`, `docs/security/**`,
`docs/architecture/**`, `apps/**`, `workers/**`, `packages/**`, migraciones, lockfiles ni
archivos raíz. No se usó Git.

## 2. Resumen del modelo

| Bloque | Cantidad | Nota |
|---|---:|---|
| `processing_activities` | 25 | `PA-01`…`PA-25`, cada una con 28 campos |
| `purposes` | 17 | Un grant para una finalidad no autoriza otra |
| `stores` | 15 | Los 9 del DFD más backups, logs, móvil, navegador, correo/push y proveedor futuro |
| `retention_policies` | 19 | Las 14 usadas por el DFD más notificación, billing, backup, telemetría y dispositivo |
| `recipient_registry` | 8 | IdP, correo, push, billing, IA, OCR, conector y cloud. **Ninguno seleccionado** |
| `rights_workflows` | 9 | Todos `pending_legal_by_category_and_jurisdiction` |
| `dpia_triggers` | 13 | |
| `gates` | 8 | Los ocho en `not_met` |
| `unresolved_decisions` | 8 | Incluye las tres dependencias heredadas |

Cobertura verificada: `F01`–`F13` completos, los 9 stores del DFD modelados **y**
referenciados por al menos una actividad, las 14 políticas de retención del DFD presentes,
y los riesgos `TM-005`, `TM-010`, `TM-011`, `TM-012` y `TM-014` cubiertos.

## 3. Comandos ejecutados y resultados

```bash
python -m tools.privacy_model.validate
python -m unittest tools.privacy_model.test_validate -v
python -m unittest discover -s tools/privacy_model -p "test_*.py"
```

| Comando | Resultado observado |
|---|---|
| `validate` | `{"errors": [], "ok": true}`, exit 0 |
| `unittest tools.privacy_model.test_validate` | `Ran 43 tests` · `OK` |
| `unittest discover -s tools/privacy_model` | `Ran 43 tests` · `OK` |

Verificación local adicional: JSON parseable (22 claves); fences Markdown balanceados en
los tres documentos (2, 4 y 2); cero merge markers; cero `TODO`/`FIXME` sin ID de tarea;
cero correos, NIT, cédulas, IP, cuentas largas o URLs externas en `docs/privacy/**` y
`tools/privacy_model/*.py`; las ocho rutas modificadas dentro del scope autorizado.

**43 pruebas en verde no demuestran por sí solas que las reglas muerdan.** Muté cinco
reglas del validador en una copia fuera del repositorio y comprobé que la suite las
detecta: duración numérica (3 fallos), delete ledger (2), company scope financiero (3),
denylist de logs (3) y atajo `requested → completed` (2). Las cinco mutaciones murieron.

No afirmo que CI esté verde: no integro CI.

### 3.1 Addendum del Integration Steward

El Integration Steward verificó que `00d9408` era un commit válido al momento de la
asignación, indexó las rutas exactas de la entrega y ejecutó el quality gate sobre ese
índice con **0 hallazgos**. La integración añadió diez pruebas negativas y reforzó el
validador para impedir: pérdida de workflows de derechos o triggers DPIA, IDs duplicados,
clasificaciones desconocidas o contradictorias, actividades sin evidencia, rutas de
borrado incompletas o inalcanzables y políticas sin revisor independiente. El total
integrado es **53 pruebas** del módulo.

El pipeline compartido incorpora ahora `tools.privacy_model.validate` y
`tools.privacy_model.test_validate`. Esto prueba coherencia del contrato, no cumplimiento
legal ni ejecución productiva de sus controles.

Quedan cuatro asuntos de arquitectura para tareas posteriores:

1. La sensibilidad del DFD y la condición de dato personal deben modelarse como dos ejes.
2. El DFD debe distinguir stores disponibles de stores efectivamente persistidos por un flujo.
3. La regla “prohibited nunca llega a raw/quarantine” exige detección S-01 antes de persistir;
   su mecanismo técnico aún no está decidido.
4. El delete ledger, los tombstones y los workflows de derechos siguen siendo contratos;
   no existe todavía una implementación productiva que los haga efectivos.

## 4. Decisiones preservadas, no resueltas

| ID | Dependencia | Cómo aparece en el mapa | Owner |
|---|---|---|---|
| `UD-PRIMARY-OPERATOR` | Atomicidad de `primary_accounting_operator` exige constraint o índice único parcial en PostgreSQL. | Declarada en `unresolved_decisions` y en §1.1 del documento. El mapa **no** apoya ninguna garantía de segregación en una comprobación en memoria. | Architecture |
| `UD-ISSUED-CONTEXT` | Falta la entidad canónica `issued_authorization_context`. | Declarada con los seis campos exigidos (`authorization_version`, company scope, purpose, principal, `issued_at`, `expires_at`) y relacionada con revocación, export, portabilidad y borrado en §10 y §12. | Architecture |
| `UD-PORTFOLIO-CANDIDATES` | La lista de companies candidatas debe venir de almacenamiento autoritativo. | `PA-21` exige `authoritative_candidate_enumeration` y `per_company_authorization`; el validador rechaza cualquier control cuyo nombre combine caché y candidatos (`PRV-PORTFOLIO-CONTROLS`). | Backend |

## 5. Hallazgos nuevos

Cinco observaciones surgidas al construir el mapa. Todas afectan a documentos fuera de mis
rutas, así que **las reporto sin editarlos**.

1. **El DFD usa una política de retención que la especificación del encargo no listaba.**
   `L-01-AUDITABLE-DECISION` aparece en `F03` y `F07` de `dfd-flows.json` pero no figuraba
   en la lista de ejemplo. La extraje dinámicamente, como pedía el encargo; una lista
   fija la habría omitido y la cobertura habría sido falsamente completa. **Vale la pena
   que el validador de DFD también extraiga dinámicamente.** Owner sugerido: Architecture.

2. **El DFD declara cuatro stores que ningún flujo persiste.** `temporal`, `valkey`,
   `analytics_projection` y `vault` están en `stores` pero no aparecen en el `persistence`
   de ningún flujo `F01`–`F13`. O falta modelar esos flujos, o el catálogo de stores
   describe capacidad instalada y no uso. Para cerrar la cobertura los referencié desde
   actividades (`PA-15` usa `temporal`, `PA-10` usa `vault`), pero **la ambigüedad está en
   el DFD, no en mi mapa**. Owner sugerido: Architecture.

3. **Las clasificaciones del DFD miden sensibilidad financiera, no sensibilidad de datos
   personales.** `public`/`internal`/`confidential`/`financial_sensitive`/`secret`/
   `prohibited` es un solo eje. Los datos de actividad laboral de un empleado de la firma
   —que `PA-20` produce al medir productividad del equipo— son `internal` en ese eje y sin
   embargo son datos personales de una persona natural. **Son dos ejes ortogonales
   colapsados en uno.** Lo mitigué con `DPIA-06` y con la advertencia de §4, pero la
   solución correcta es una dimensión de clasificación separada. Owner sugerido: Privacy +
   Architecture.

4. **`L-01-DELETE-LEDGER` debe sobrevivir a la ventana de backup más larga.** Si el ledger
   caduca antes que el backup que debe corregir, el tombstone deja de poder reaplicarse y
   la supresión se vuelve reversible sin que nadie lo note. Lo dejé escrito en §8 del
   documento y en el campo `expiry_trigger` de la política, pero **la relación de orden
   entre ambas duraciones es una decisión de L-01** y hoy no existe. Owner sugerido:
   Legal + Platform.

5. **El reloj de retención financiera no puede arrancar en la fecha de carga.**
   `L-01-FINANCIAL` computa desde el último asiento o documento relacionado. Si el
   lifecycle del object store contara desde `created_at`, borraría antes de tiempo el
   soporte de un periodo reabierto o de una carga tardía. Es un error barato de cometer y
   caro de descubrir. Owner sugerido: Legal + Data Engineering.

## 6. Riesgos y bloqueos

1. **El mapa describe intención, no implementación.** Ninguna regla de este modelo está aplicada por código productivo: no hay RLS, ni purga, ni ledger, ni reaplicación de tombstones ejecutándose. El validador comprueba que el **contrato** sea coherente, no que el sistema lo cumpla.
2. **Los roles responsable/encargado son posturas candidatas.** Ninguna está aceptada. Si Legal reclasifica una actividad, cambian sus derechos aplicables, su retención y su régimen de transmisión. Es el mayor riesgo de reproceso de la Parte de privacidad.
3. **Sin A-02 no hay evaluación de transmisión posible.** Todo `cross_border_state` está pendiente. No se puede firmar DRG-00 con esta pieza abierta.
4. **Sin L-01 no hay duración.** El modelo prohíbe estructuralmente inventar plazos, lo que es correcto, pero significa que la política de retención **no es operable todavía**.
5. **`base_sha: 00d9408` no fue verificado.** El encargo prohíbe Git. Registro el valor declarado, sin comprobación.
6. **No ejecuté `python -m tools.quality_gate.cli`.** Ese scanner opera sobre el índice de Git y mis archivos son nuevos y no indexados: no los cubriría. Queda `pending_integration_steward`.
7. **Desviación de herramienta declarada.** El encargo pedía `apply_patch`; esa herramienta no está disponible en mi entorno. Usé escritura y edición directa de ficheros, sin Git y sin salir del scope. El efecto sobre el árbol de trabajo es el mismo; lo declaro para que la revisión no asuma un mecanismo que no usé.

## 7. Dependencias

| Depende de | Para qué |
|---|---|
| `FNC-ARC-002` (`dfd-flows.json`) | Flujos, stores, clasificaciones, denylist de logs y políticas de retención |
| `FNC-SEC-002` (`threat-model.json`) | Riesgos `TM-005`, `TM-010`, `TM-011`, `TM-012`, `TM-014` |
| `FNC-DOM-001` (`TENANCY_MODEL.md`) | Company como frontera, engagement revocable, `authorization_version` |
| `FNC-SEC-001` (`RBAC_ABAC_SOD.md`) | Finalidad como límite de grant, SoD, break-glass, denegación uniforme |
| `FNC-DAT-001` (`SYNTHETIC_DATA_POLICY.md`) | Techo `synthetic_only` y definición de dato real derivado |
| `A-02`, `L-01`, `L-02` | Región, retención e IA externa. Bloquean DRG-00 y DRG-01 |

## 8. Revisiones solicitadas

- **Privacy (owner).** Inventario de 25 actividades, minimización por actividad, workflows de derechos y enrutamiento responsable/encargado, y el hallazgo 3 sobre clasificación de datos personales.
- **Legal (owner).** Matriz de roles de §3: ninguna postura está aceptada. Bases jurídicas, régimen de transmisión frente a transferencia, plazos de retención (L-01), relación de orden del hallazgo 4, plazo de notificación de incidentes y aplicabilidad de derechos por categoría de sujeto.
- **Security.** Stores y sus prohibiciones, allowlist de logs contra la denylist del DFD, soporte y break-glass, delete ledger fuera del restore y reaplicación de tombstones.
- **Architecture.** Hallazgos 1 y 2 sobre el DFD, las tres dependencias heredadas y la coherencia con C4/DFD.
- **Product.** `PA-20` analítica operativa, `PA-11` notificaciones y la medición de productividad individual del equipo de la firma.

## 9. Rollback

Eliminar los ocho ficheros listados en §1. No hay esquema, migración, lockfile, CI,
Compose ni configuración compartida que revertir, y ningún artefacto de otro agente fue
tocado. El repositorio vuelve exactamente al estado previo.

## 10. Declaración expresa

Esta entrega **no supera S1-READY**, **no supera DRG-00** y no autoriza datos reales,
piloto, región, proveedor, IA externa ni publicación de precios. Los ocho gates permanecen
en `not_met` y `pending_human`. Ningún riesgo residual queda aceptado. Ninguna base
jurídica queda fijada. Ninguna duración de retención queda decidida.
