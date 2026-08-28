---
task_id: FNC-PRV-002
status: REVIEW_PENDING
base_sha: 475bd8802472f126f01532af19b52799e1ffc955
reservation_sha: 0df647c
implementation_sha: 695e8a5
tested_head_sha: 695e8a5ad2f82d445622ece853d40b55ce21d480
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [abogado colombiano nominal, Privacy, Security, Accounting]
---

# Handoff FNC-PRV-002 — matriz ejecutable L-01

## Resultado

La matriz deriva las 19 políticas vigentes del mapa de privacidad, queda ligada
a su representación JSON canónica y separa estrictamente dos estados:

- `review_pending`: todas las decisiones humanas vacías, L-01 cerrado.
- `adjudicated`: sólo válido si las 19 filas, abogado y cuatro signoffs
  independientes están completos.

El borrador integrado está en el primer estado. No contiene plazos, nombres,
contratos ni conclusiones. El reporte devuelve `ok: true` junto a
`human_adjudication: false`, `l01_met: false` y
`real_data_authorized: false`; no puede confundirse con autorización.

## Contrato implementado

Cada futura decisión exige días calendario exactos, fundamento, contrato,
excepciones, fecha efectiva y referencia de revisión. Los hechos técnicos —
stores, reloj, derivados, purga, hold, backup y restore— se leen de la fuente,
por lo que la matriz no puede debilitarlos duplicando una versión conveniente.

Las guardas exigen alcance autoritativo por company, tombstone previo, inventario
de derivados y exports, hold documentado, reconciliación antes de completar y
reaplicación de tombstones antes de reabrir un restore.

Una fixture adjudicada completamente sintética demuestra que el esquema futuro
es utilizable: 19 decisiones, cuatro revisores distintos y únicamente L-01 en
`met`. Aun ahí DRG-00/DRG-01 y `real_data_authorized` permanecen falsos.

## Hallazgos fijados como invariantes

1. `L-01-FINANCIAL` empieza en el último asiento o documento relacionado, no en
   el upload; el validador mata el retroceso.
2. `L-01-DELETE-LEDGER` debe superar estrictamente a `L-01-BACKUP`; igualarlos
   mata la adjudicación.
3. Restore no reabre servicio sin reaplicar tombstones y reconciliar.
4. Una decisión parcial, un `bool` disfrazado de entero, plazo cero o mayor a
   36.500 días, evidencia con correo, firma del Founder o revisores repetidos
   falla cerrada.

## Evidencia reproducible

| Verificación | Resultado |
|---|---|
| `python3 -B -m unittest tools.retention_matrix.test_model` | 29/29 OK |
| Legal + retención | 55/55 OK |
| `python3 -B -m tools.retention_matrix validate` | exit 0; 19 pendientes; sin autorización |
| `python3 -B -m tools.privacy_model.validate` | OK, sin regresión |
| `python3 -B -m tools.quality_gate.cli` sobre índice | OK, 0 findings |
| `git diff --cached --check` | OK |

## Trabajo humano y bloqueos

- Legal: adjudicar 19 plazos y fundamentos con abogado distinto del Founder.
- Privacy: derechos, categorías, derivados y supresión.
- Security: hold, delete ledger, backup, restore y evidencia.
- Accounting: relojes de financial/close/billing y reaperturas.

Las personas deben ser distintas para los cuatro signoffs. La evidencia sensible
se custodia fuera de Git y el repositorio sólo recibe alias/referencias estables.
FNC-LEG-001 sigue pendiente de abogado; A-02 y S-01 también permanecen abiertos.
Por ello no se debe cargar todavía ningún documento real, ni siquiera “de prueba”.

## Rollback

Revertir `695e8a5` elimina matriz, herramienta y solicitud; revertir `0df647c`
elimina su reserva. No existen migraciones, lifecycles aplicados, borrados,
infraestructura ni datos que restaurar.
