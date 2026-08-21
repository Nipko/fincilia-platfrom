---
task: FNC-PLT-003
status: REVIEW_PENDING
base_sha: 6bca7ea
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-PLT-003

## Entrega

- Workflow CI con permisos read-only y actions fijadas por SHA.
- Dos jobs: política/corpus y stack PostgreSQL/RLS/worker.
- Escáner local de política sin dependencias externas.
- Siete tests positivos/negativos del escáner.
- Dependabot semanal para Actions, npm y Docker.
- Documentación de operación, supply chain y límites.

## Verificación local observada

| Verificación | Resultado |
|---|---:|
| `python -m tools.quality_gate.cli` | PASS, 0 hallazgos |
| Tests quality gate | 7/7 PASS |
| Tests corpus | 12/12 PASS |
| Corpus byte a byte | PASS, 5 archivos, 0 errores, 2 warnings intencionales |
| Compose config | PASS |
| `npm ci --ignore-scripts` | PASS |
| `npm audit --audit-level=high` | PASS, 0 vulnerabilidades reportadas |
| TypeScript | PASS |
| Vitest RLS/outbox | 5/5 PASS |
| Worker Python | 3/3 PASS |
| YAML local | PASS mediante parser disponible en el entorno |

## Decisiones

- No se usa `pull_request_target` ni permisos write.
- No se suben artifacts.
- El stack spike sigue siendo descartable.
- La política inspecciona el índice Git para que local y CI compartan el mismo universo.
- Los checks profesionales administrados complementarán, no sustituirán, este gate.

## Pendientes

- Security y Architecture deben revisar reglas, falsos positivos y acciones allowlisted.
- FNC-GOV-001 debe asignar owners antes de configurar CODEOWNERS nominal.
- El administrador del futuro remoto debe activar branch protection y secret scanning.
- Una ejecución real de GitHub Actions debe confirmar nombres finales de checks y compatibilidad del runner.
- SBOM, escaneo de imágenes/SCA ampliado y firma de artefactos corresponden al hardening posterior.

## Rollback

Retirar workflow, Dependabot, `tools/quality_gate`, documentación y handoff. No hay despliegues, secretos, migraciones ni datos reales que revertir.

Esta tarea no supera S1-READY ni autoriza DRG-00.
