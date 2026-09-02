---
task_id: FNC-MAP-002
status: REVIEW_PENDING
base_sha: 6ff14cc679c3133cffeb45a625cd0b527b0f740d
tested_head_sha: 84f03ff2c8886d7863f1d1ca14636f53a3879166
ci_run: 33601151681
ci_status: success
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Data, Database, Security, Backend/Architecture, QA]
---

# Handoff FNC-MAP-002 — version de mapeo inmutable

## Resultado

El `UPDATE` que el runtime necesita para validar una version ya no equivale a
permiso para reescribirla. PostgreSQL conserva identidad, plantilla, artefacto,
definicion, digests, autor y fecha, y aplica la maquina cerrada
`draft -> validated -> superseded`.

El endpoint existente de validacion sigue funcionando e idempotente. No se
agrego una ruta de supersession ni se cambio la semantica del mapeo.

## Cambios

- V0055 agrega `enforce_mapping_version_update`, con `search_path` fijado,
  `PUBLIC` revocado y sin `SECURITY DEFINER`.
- Un cambio de payload o identidad falla con
  `ck_mapping_version_immutable`.
- Un salto, retroceso, cambio de validador o resurreccion falla con
  `ck_mapping_version_state_transition`.
- Se permiten solamente un UPDATE idempotente, `draft -> validated` con
  metadatos completos y `validated -> superseded` conservandolos.
- El nombre del trigger conserva primero el error especifico de fuente de
  FNC-MAP-001 cuando ambos controles aplican.

## Evidencia

| Verificacion | Resultado |
|---|---|
| V0055 apply + replay | `head: V0055`; segundo run sin cambios |
| prueba adversarial PostgreSQL | mutacion JSON, rollback de estado y resurreccion rechazados; validacion API y supersession legitima aceptadas |
| fuente + inmutabilidad focales | 2, OK |
| P3 + conciliacion completas | 48, OK |
| contratos de migracion | 66, OK |
| work graph / quality gate | 134 tareas sin huerfanos; `ok: true`, cero hallazgos |
| CI del codigo definitivo | run `33601151681`: success; ciclo integral, navegador y WCAG incluidos |

## Hallazgos de ejecucion

1. La tabla concedia `UPDATE` completo aunque el producto solo actualizaba
   estado, validador y fecha. Los comentarios prometian una version inmutable,
   pero PostgreSQL no la imponia.
2. La API normaliza `last_data_row` ausente a `null`. La prueba conserva el
   snapshot JSONB realmente persistido antes del ataque y comprueba que sea
   identico despues, en vez de comparar con un input abreviado.
3. El trigger especifico de fuente debe ejecutarse antes que el general para
   mantener errores adjudicables. Los nombres se eligieron y probaron con ese
   orden.

## Riesgos y revisiones

- Data/Accounting debe confirmar que todo cambio de definicion crea otra
  version y que `superseded` nunca vuelve a ser elegible para trabajo nuevo.
- Database/Security debe revisar maquina de estados, ACL y orden de triggers.
- Backend/QA debe revisar compatibilidad del endpoint de validacion y pruebas
  de mutacion directa.
- No se acepto ADR, gate ni revision humana. El alcance sigue sintetico.

## Commits y rollback

1. `a7faae5` — contrato, reserva y trazabilidad inicial.
2. `bde9d4f` — V0055 y pruebas adversariales.

V0055 es forward-only. Una base aplicada solo se corrige mediante una migracion
compensatoria posterior; no se debe editar ni retirar el fichero. No existe
dato financiero real que purgar.
