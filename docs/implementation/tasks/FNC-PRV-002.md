---
id: FNC-PRV-002
title: Matriz ejecutable L-01 de retención y borrado
epic: FNC-EP-002
phase: F0
iteration: E1
type: privacy_readiness
status: review_pending
priority: P0
accountable_owner: FOUNDER-01
agent_lane: Privacy/Legal
implementer: Codex principal dev + Integration Steward
independent_reviewer: abogado colombiano nominal + Privacy + Security + Accounting
dependencies: [FNC-PRV-001, FNC-LEG-001]
gate: L-01
gate_effect: none
allowed_data: synthetic_only
security_impact: high
privacy_impact: high
risk_ids: [TM-005, TM-014]
---

# Resultado esperado

Una matriz versionada deriva todas las políticas de retención del privacy-map y
obliga a adjudicar, por política, plazo operativo exacto, evento de inicio,
fundamento, legal hold, derivados, purga, backup, restore y evidencia. Mientras
falte una sola adjudicación o revisión nominal, L-01 y los gates de datos reales
permanecen cerrados.

# Base y modalidad

- Base: `475bd8802472f126f01532af19b52799e1ffc955`.
- Rama: `main`; Integration Steward es el único ejecutor Git.
- Dependencia Legal: FNC-LEG-001 está estructuralmente listo pero aún requiere
  abogado. Esta tarea prepara la adjudicación; no la suplanta.
- Datos: sólo metadatos de política y fixtures sintéticos.

# Dentro de alcance

- Modelo JSON fresco respecto de `privacy-map.json`.
- Cobertura dinámica y exacta de todas las políticas de retención.
- Estados separados `pending_human` y `adjudicated`.
- Reglas ejecutables de borrado, derivados, tombstone, backup y restore.
- Restricción: delete ledger sobrevive a la ventana de backup más larga.
- CLI validate/report, pruebas adversariales, documento y solicitud de revisión.
- Handoff y registros centrales por Integration Steward.

# Fuera de alcance

- Elegir plazos, fundamento o excepciones en nombre de Legal/Privacy.
- Modificar privacy-map, aplicar lifecycle cloud, borrar datos o crear migraciones.
- Recibir datos reales, mover L-01/DRG-00/DRG-01 o aceptar riesgo residual.
- Implementar workflows productivos de derechos, borrado o restore.

# Rutas permitidas

- `docs/privacy/retention-deletion-matrix.json`
- `docs/privacy/RETENTION_DELETION_MATRIX.md`
- `tools/retention_matrix/**`
- ficha, handoff y solicitud de decisión de esta tarea.
- registros centrales por Integration Steward.

# Rutas prohibidas

- `docs/privacy/privacy-map.json` y `tools/privacy_model/**`.
- Producto, migraciones, CI, infraestructura, locks y ADR aceptados.
- PII, documentos financieros o evidencia jurídica sensible.

# Criterios de aceptación

- **AC-01.** Las 19 políticas vigentes se derivan dinámicamente y la fuente está
  ligada por SHA-256; una alta, baja o cambio invalida la matriz.
- **AC-02.** El borrador válido conserva plazo, fundamento y revisor en null,
  `L-01: not_met` y `real_data_authorized: false`.
- **AC-03.** Una matriz adjudicada sólo sería válida con cada fila completa,
  abogado distinto del Founder y signoffs nominales independientes.
- **AC-04.** Inicio, stores, derivados, purga, hold, backup y restore coinciden
  con la fuente y no pueden relajarse en la matriz.
- **AC-05.** El delete ledger dura más que el backup de mayor ventana y restore
  reaplica tombstones antes de reabrir servicio.
- **AC-06.** Ningún estado de la matriz, por sí solo, autoriza DRG-00/DRG-01.
- **AC-07.** Mutaciones críticas mueren y los reportes separan validez técnica,
  decisión humana y autorización de datos.
- **AC-08.** Unitarias, quality gate, grafo y handoff reproducible pasan.

# Handoff

Legal y Privacy deben completar plazos y fundamentos. Accounting valida los
eventos de inicio financieros; Security valida hold, tombstones y restore. El
Founder sigue accountable provisional, pero no cuenta como revisor independiente.
