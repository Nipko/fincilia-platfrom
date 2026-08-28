---
id: FNC-LEG-001
title: Plantilla ejecutable de tratamiento para corpus real de investigación
epic: FNC-EP-002
phase: F0
iteration: E1
type: legal_readiness
status: in_progress
priority: P0
accountable_owner: FOUNDER-01
agent_lane: Legal/Privacy
implementer: Codex principal dev + Integration Steward
independent_reviewer: abogado colombiano nominal + Privacy + Security
dependencies: [FNC-GOV-001, FNC-PRV-001]
gate: DRG-00
gate_effect: none
allowed_data: synthetic_only
security_impact: high
privacy_impact: high
risk_ids: [TM-005, TM-014]
---

# Resultado esperado

Una plantilla contractual y de concepto jurídico, legible y ejecutable, obliga
a definir por actividad las partes, roles, alcance, finalidades, instrucciones,
categorías, titulares, operaciones, receptores, región, subencargados, medidas,
incidentes, derechos, retención, devolución, borrado, restore, auditoría y
terminación antes de recibir el primer artefacto real de investigación.

La entrega prepara la revisión de un abogado; no constituye asesoría jurídica,
no adjudica el rol de Fincilia, no acepta un proveedor o región y no firma ni
habilita DRG-00. Sólo un abogado colombiano nominal puede aprobar el resultado.

# Base y modalidad

- Base: `e446d1ddc77102ba1464615cfbbb2f0e5dec5d7e`.
- Rama: `main`, Integration Steward como único ejecutor Git.
- Datos: únicamente contratos y fixtures sintéticos; ningún nombre, documento,
  NIT, correo, firma o información financiera real.

# Dentro de alcance

- Modelo JSON fail-closed de la plantilla y del estado de revisión.
- Documento Markdown listo para completar por Legal, con campos explícitos.
- Cobertura dinámica de actividades DRG-00/DRG-01 del privacy map.
- Bloqueo de roles definitivos mientras `UD-ROLE` esté abierto.
- Bloqueo de región/proveedor mientras A-02/`UD-PROVIDERS` estén abiertos.
- Bloqueo de plazos definitivos mientras L-01 esté abierto.
- CLI de `validate` y `report`, pruebas negativas y documentación de fuentes.
- Handoff y registros centrales por Integration Steward.

# Fuera de alcance

- Dar concepto jurídico, representar a Fincilia o firmar un contrato.
- Aceptar Responsable/Encargado, base jurídica, autorización, país, proveedor,
  subencargado, plazo, SLA legal o riesgo residual.
- Contactar clientes, abogados o proveedores en nombre del usuario.
- Recibir datos reales, habilitar flags, crear infraestructura o cerrar gates.
- Implementar IdP, MFA, invitaciones, retención o borrado productivo.

# Rutas permitidas

- `docs/legal/**`
- `tools/legal_treatment/**`
- `docs/implementation/tasks/FNC-LEG-001.md`
- `docs/implementation/handoffs/FNC-LEG-001.md`
- `docs/implementation/decision_requests/FNC-LEG-001-LEGAL-REVIEW.md`
- registros centrales por Integration Steward.

# Rutas prohibidas

- Código de producto, base de datos, migraciones, CI, infraestructura y locks.
- Privacy map, DFD, threat model, ADR aceptados y estados humanos existentes.
- Cualquier dato personal o financiero real.

# Criterios de aceptación

- **AC-01.** El modelo sólo admite `synthetic_only`, `review_pending` y
  `human_approval: false` mientras falte abogado nominal.
- **AC-02.** Cada actividad que privacy-map asigna a DRG-00 o DRG-01 aparece una
  vez, por extracción dinámica, con rol y aplicabilidad pendientes.
- **AC-03.** La plantilla contiene alcance, actividades, obligaciones del
  encargado y garantías de seguridad, sin presentarlas como cláusulas aprobadas.
- **AC-04.** Derechos, incidentes, confidencialidad, minimización, instrucciones,
  auditoría, devolución/supresión, restore y terminación son campos obligatorios.
- **AC-05.** A-02, L-01, `UD-ROLE` y `UD-PROVIDERS` permanecen visibles y
  cualquier adjudicación incompatible hace fallar la validación.
- **AC-06.** Fuentes oficiales, fecha de consulta y preguntas para Legal quedan
  trazables sin copiar extensamente texto protegido.
- **AC-07.** Mutaciones de aprobación, datos reales, actividad omitida, región,
  rol o retención prematuros mueren.
- **AC-08.** Quality gate, grafo, unitarias y handoff reproducible pasan.

# Handoff

Legal debe completar y firmar un concepto nominal. Privacy revisa derechos,
retención y categorías; Security revisa medidas e incidentes. Una aprobación de
esta plantilla no decide A-02 ni L-01 y por sí sola no supera DRG-00.
