---
task_id: FNC-REC-007
status: REVIEW_PENDING
base_sha: ba91e70
implementation_sha: 6b29121
tested_sha: 2bc936a
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Security, Backend/Architecture, UX/QA]
---

# Handoff FNC-REC-007 — productividad segura de conciliacion

## Resultado

El explorador de candidatos permite filtrar por relacion de referencia con tres
modos cerrados: `all`, `matching` y `different`. El modo se valida y aplica en el
servidor, se devuelve en el contrato y se conserva en formulario, URL y
paginacion. No cambia la generacion de candidatos ni sus reglas de fecha,
importe decimal exacto, moneda o direccion opuesta.

Las referencias se normalizan con la semantica determinista ya usada por el
dominio. `matching` solo conserva igualdad normalizada; `different` conserva el
complemento. Un valor fuera del enum se rechaza con 422 antes de consultar.

## Evidencia reproducible

- 16 pruebas unitarias del motor de conciliacion dentro de la corrida UAT.
- pruebas API de default, los tres modos y modo invalido.
- 9 pruebas PostgreSQL focales compartidas, incluidas consultas con RLS y
  rechazo del enum invalido.
- 42 recorridos Chromium en la regresion integral; el filtro persiste en URL y
  paginacion.
- dos corridas UAT completas y limpias sobre `2bc936a`.

## Limites, revision y rollback

La entrega no agrega score, similitud, tolerancia monetaria, ranking, auto-match,
confirmacion, efecto financiero, cierre ni certificacion. El cliente no aporta
una empresa confiable: la autorizacion y el contexto siguen resueltos server-side.

Accounting debe confirmar la semantica de referencias vacias; Security y
Backend/Architecture la frontera RLS; UX/QA la claridad del filtro y su estado
navegable. Ninguna revision independiente ha sido aceptada.

Revertir `6b29121` elimina el modo de referencia sin modificar datasets,
decisiones o movimientos existentes.

## Rutas liberadas

Motor, ruta y pruebas de conciliacion API; cliente, estacion y pruebas web;
pruebas PostgreSQL focales, ficha, handoff y registros centrales.
