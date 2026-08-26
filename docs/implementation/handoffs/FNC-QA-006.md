---
task_id: FNC-QA-006
status: REVIEW_PENDING
base_sha: 774575cfc01529016e9ae189d760993376962ead
reservation_sha: ed44a82
tested_head_sha: 104f44bd41e3003a8d9fb92b22d5aef8b507c274
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Platform, QA, Security, Accessibility/Product]
---

# Handoff FNC-QA-006 — aceptación web y arranque coherente

## Resultado

El camino local construye API, worker, web y migrador desde la revisión actual,
detiene aplicaciones anteriores antes de migrar, recrea las aplicaciones y falla
si el readiness no confirma producto y esquema. Los volúmenes conservan sus
nombres por defecto y admiten nombres explícitos para una aceptación aislada.

La web prueba automáticamente el límite de portafolio y rol: Ana ve sus dos
empresas y capacidades de preparación; Beto sólo Panadería, capacidades de
revisión y ninguna carga; una URL de Transportes no le revela sus datos. Se
amplió Axe al portafolio autenticado y a la denegación cross-company.

No se tocaron API, worker, DB, migraciones, móvil, contratos, permisos, RLS,
semántica financiera, ADR ni gates. Todo dato ejecutado fue sintético local.

## Cambios

- `infra/local/up.sh`: build actual, stop conservador, migración/seed, recreación
  explícita y sonda `/health/ready` con dependencia `schema=up`.
- `infra/local/compose.yaml`: overrides opt-in para los dos volúmenes persistentes,
  manteniendo los nombres históricos como defaults.
- `tools/local_stack`: contrato y 37 pruebas; cada fase y cada aserción de
  readiness muerde por separado, incluido el orden.
- `apps/web/tests/e2e`: tres casos de rol/tenancy y dos superficies Axe nuevas.

## Matriz de aceptación

| Criterio | Evidencia |
|---|---|
| AC-01..AC-03 | corrida limpia aplicó V0001..V0016, recreó las imágenes y confirmó `ready` + `schema up` |
| AC-04 | contrato rechaza `--volumes`, prune y variantes destructivas |
| AC-05 | 37 pruebas de `tools.local_stack`, incluidas cinco mutaciones de fase, tres de readiness y orden |
| AC-06 | E2E Ana: exactamente Panadería y Transportes, rol preparer, `dataset.map` y carga visible |
| AC-07..AC-08 | E2E Beto: una empresa, rol reviewer, `dataset.publish`, sin carga y denegación directa neutral |
| AC-09 | los tres recorridos de carga de 25 MiB, 25 MiB + 1 y bypass BFF pasan |
| AC-10 | 4/4 Axe, sin hallazgos críticos o serios |
| AC-11 | verificación visible previa: Beto mostró controles de revisión de corrección; no se pulsó aprobar ni rechazar |
| AC-12 | validadores local stack, work graph, catálogo y quality gate verdes; supply chain/S1 se declaran abajo |
| AC-13 | este handoff contiene base, head probado, evidencia, riesgos y rollback |
| AC-14 | corrida `fincilia_qa006_*` nació vacía; el volumen habitual no se borró ni se modificó |

## Evidencia ejecutada

| Verificación | Resultado |
|---|---|
| `tools.local_stack.test_validate` | **37**, OK |
| `tools.local_stack.validate` | `ok: true` |
| `infra/local/up.sh` con volúmenes aislados | V0001..V0016 aplicadas, seed sintético y readiness OK |
| Web lint + TypeScript | OK |
| Web unitarias | **79** en 14 archivos, OK |
| Web build Next production | OK, 11 rutas |
| Playwright Chromium | **9**, OK |
| Playwright/Axe | **4**, OK |
| PostgreSQL real, orden CI | **286**, OK, 1 omitida por diseño |
| API dentro de imagen fijada | **70**, OK |
| Worker dentro de imagen fijada | **18**, OK |
| `npm audit --audit-level=high` | 0 vulnerabilidades |
| work graph | `ok: true`, 68 tareas y una reserva antes de liberarla |
| test catalog | `model_valid: true`, 0 blockers; 13 planned y 41 contractuales no implementados |
| quality gate | `ok: true`, 0 findings; se repite sobre el índice final antes del commit |

## Hallazgos de ejecución

1. El volumen habitual registra V0016 con checksum `440160...`, mientras el
   único archivo integrado tiene checksum canónico `a03b09...`. Es evidencia de
   la versión transitoria usada durante la integración fallida anterior. El
   migrador abortó correctamente; no se editó el ledger ni se borró el volumen.
2. La primera corrida de esquema se hizo con el worker vivo. El worker alcanzó a
   referenciar un `processing_run` durante el teardown y produjo una FK. En el
   orden real de CI —aplicaciones detenidas— los 286 casos pasaron.
3. El caso de 100.000 movimientos midió 41,5 s totales en la primera corrida y
   64,5 s al repetir sobre el volumen ya cargado; `prepare` quedó en 57,5 s y la
   guarda vigente pasó. La degradación por acumulación debe medirse en el carril
   manual de rendimiento antes de afirmar capacidad sostenida.
4. `s1_readiness evaluate` y la suite monolítica de herramientas quedaron
   atrapados repetidamente en el hijo `tools.supply_chain.cli validate` con E/S
   sobre el filesystem Windows. Se interrumpieron después de ventanas acotadas;
   no se presentan como verdes. La evidencia supply-chain ya figuraba stale y
   bloqueante en S1.

## Estado de gates y límites

- S1-READY sigue `not_met`. La última evaluación completa válida tenía 29/30
  comprobaciones de máquina en pass y 11 blockers; esta tarea no los acepta.
- Permanecen 11 ADR requeridos no listos, 10 decisiones humanas abiertas y siete
  slots nominales sin asignar. DRG-00/DRG-01 no cambian.
- El flujo completo de corrección visible no tiene fixture E2E seed-only: crear
  uno exigiría aprobar sintéticamente una release humana. Se conserva la prueba
  PostgreSQL y la comprobación manual sin decisión.
- El stack que queda ejecutándose usa los volúmenes sintéticos aislados
  `fincilia_qa006_pgdata` y `fincilia_qa006_objectdata`; el volumen habitual queda
  intacto para una decisión explícita posterior.

## Commits y rollback

1. `ed44a82` — ficha, backlog y reserva.
2. `ef4763a` — arranque coherente, volúmenes aislados y contrato ejecutable.
3. `104f44b` — E2E de roles/tenancy y Axe autenticado.

Revertir 3 retira sólo pruebas. Revertir 2 restaura el arranque anterior y los
nombres fijos de volumen; no elimina ningún volumen. No ejecutar `down --volumes`
como rollback. Los volúmenes de aceptación sólo se retiran después de verificar
sus nombres exactos y cuando ya no se necesite la plataforma para pruebas.

## Revisión independiente pendiente

- Platform: orden build/migrate/recreate, comportamiento fail-closed y overrides.
- Security: denegación neutral, fronteras de rol y ausencia de secretos.
- QA/Accessibility/Product: alcance del recorrido y superficies Axe.
- Performance owner: degradación medida al repetir 100.000 movimientos.
