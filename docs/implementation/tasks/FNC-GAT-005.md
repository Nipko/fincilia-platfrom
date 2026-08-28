---
id: FNC-GAT-005
title: Readiness ejecutable del piloto privado con datos reales
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 5b0fcc2
gate: DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Legal/Privacy, Security, Platform/SRE, QA]
---

# Resultado

Un contrato ejecutable consolida DRG-00 y DRG-01 sin confundir una beta de
usabilidad con autorización para procesar información financiera real. Cada
control distingue evidencia automática de aprobación humana y falla cerrado.

# Alcance inicial del piloto

- Un fundador, una empresa y hasta tres usuarios nominales invitados.
- Extractos, auxiliares y facturas propios en CSV/XLSX/PDF.
- Se excluyen tarjetas, nómina, identificaciones oficiales, salud, credenciales,
  conectores, correo, SFTP, webhooks, IA externa y cierres automáticos.
- AWS São Paulo permanece como dirección del Founder pendiente de revisión
  independiente Legal/Privacy y Architecture/Security.

# Criterios de aceptación

1. DRG-00 es requisito duro de DRG-01 y no puede omitirse.
2. Un control humano solo cuenta con revisor nominal distinto de `FOUNDER-01`,
   fecha y evidencia existente.
3. Un control técnico solo cuenta con evidencia reproducible existente.
4. Los canales no implementados se prueban deshabilitados, no “asegurados”.
5. `real_data_authorized` se deriva de todos los controles; no es una bandera
   libre.
6. La selección AWS/región no equivale a concepto legal ni DPA aceptado.
7. El informe enumera blockers por gate, owner y tipo.

# Fuera de alcance

Marcar DRG-00/01 cumplidos, emitir concepto jurídico, ejecutar pentest
independiente, aceptar riesgos residuales o cargar un documento real.
