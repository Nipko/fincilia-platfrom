---
task_id: FNC-DB-004
status: REVIEW_PENDING
base_sha: 1daf11d
reservation_sha: bf4e3db
implementation_sha: a18d62e
tested_head_sha: a18d62e
integration_sha: pending_handoff_commit
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Architecture, Security, QA]
---

# Handoff FNC-DB-004 — concurrencia, outbox y fencing en PostgreSQL

## Resultado

El laboratorio descartable demuestra contra PostgreSQL 17 real las tres
invariantes que FNC-DOM-007 no podía probar mediante lógica pura:

- `TST-IDEM-001`: dos sesiones compiten por el mismo trabajo y sólo una obtiene
  el reclamo; la otra no espera indefinidamente ni crea una segunda ejecución.
- `TST-IDEM-004`: el efecto de dominio y el outbox son atómicos; un fallo
  inyectado revierte ambos, mientras un evento confirmado sobrevive a la caída
  anterior a entrega y sólo registra una recepción.
- `TST-IDEM-005`: un lease nuevo incrementa el fencing token y el worker con el
  token expirado ya no puede escribir efecto, outbox ni finalizar el trabajo.

El runtime sólo puede invocar una lista cerrada de funciones `SECURITY DEFINER`.
No tiene DDL ni escritura directa en tablas. Compose no publica puertos, usa un
proyecto fijo y la imagen PostgreSQL ya fijada por digest. El runner no usa shell,
limita argumentos, roles, entorno, rutas y salida, y convierte un fallo de limpieza
en fallo de la ejecución.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| Contrato ejecutable | válido, 0 errores |
| Pruebas de contrato y seguridad del runner | 25/25, OK |
| PostgreSQL real, repetición 1 | 3/3 invariantes, OK |
| PostgreSQL real, repetición 2 | 3/3 invariantes, OK |
| Privilegios efectivos | runtime sin DDL ni escrituras directas, OK |
| Limpieza confinada | contenedor, volumen y red exactos eliminados, OK |
| Modelo de idempotencia existente | válido, sin regresión |
| Catálogo ejecutable | `TCM-CONTRACT-NOT-IMPLEMENTED` 41 → 38 |
| Grafo de trabajo | válido, 88 tareas y 219 aristas |
| Quality gate sobre índice | OK, 0 hallazgos |

Comandos principales:

```text
python -m tools.concurrency_spike.validate
python -m unittest tools.concurrency_spike.test_validate -v
python -m tools.concurrency_spike.cli run --repeat 2
python -m tools.idempotency_model.validate
python -m tools.test_catalog.cli validate
python -m tools.work_graph.validate
python -m tools.quality_gate.cli
```

La corrida real usó Docker Engine 29.7.2 disponible mediante WSL. La salida
esperada de la inyección de fallo es código 3; el runner sólo la considera válida
si las consultas posteriores demuestran ausencia de efecto y de evento parciales.

## Hallazgos y límites

1. La limpieza no puede ser sólo una cláusula `finally`: su resultado debe cambiar
   el veredicto. El runner ahora devuelve `cleanup_failed` si queda recurso o falla
   el `compose down` confinado.
2. El patrón de claim/fencing es compatible con las invariantes ya declaradas, pero
   este spike no certifica que cada implementación productiva sea equivalente.
3. El laboratorio demuestra semántica de PostgreSQL, no selecciona broker, motor
   de workflows ni arquitectura de despliegue.
4. No se modificaron migraciones productivas, API, worker, web, Compose local, CI,
   contratos financieros, ADR ni gates.

Architecture debe revisar la correspondencia entre trabajo, ejecución, efecto y
outbox; Security, la superficie de funciones definer y privilegios; QA, el método
de concurrencia, repetición y prueba negativa. Ninguna de esas revisiones se
autoacepta. `FOUNDER-01` y el implementador no cuentan como revisores
independientes.

## Rollback y rutas liberadas

Revertir `a18d62e` elimina únicamente el contrato, runner y laboratorio. No queda
estado persistente: cada ejecución elimina el proyecto Compose exacto, su volumen
y su red. No usar borrados amplios ni afectar el stack `fincilia-local`.

Rutas liberadas: `spikes/FNC-DB-004/**`, `tools/concurrency_spike/**`,
`docs/database/concurrency-spike.json`, `docs/database/CONCURRENCY_SPIKE.md`, ficha
y handoff de FNC-DB-004. S1-READY no cambia por esta entrega.
