---
task_id: FNC-WEB-005
revision: R1
status: REVIEW_PENDING
supersedes_evidence_only: docs/implementation/handoffs/FNC-WEB-005.md
tested_code_sha: c2a95de
orchestration_sha: 24a467f
data_ceiling: synthetic_only
gate_effect: none
independent_reviewers: [Product, Accounting, Privacy, Accessibility/QA]
---

# FNC-WEB-005 R1 — aceptación web integral posterior al handoff

Esta adenda no cambia el alcance ni reescribe el handoff inicial. Añade la
evidencia obtenida al ejecutar el runner UAT completo contra dos instalaciones
aisladas de la revisión entregada.

## Resultado ejecutado

| Fase | Resultado |
|---|---|
| Instalación vacía | V0001–V0057 aplicadas; sin semilla inicial |
| Alta desde cero | 1/1 Chromium; crea identidad sintética y primer espacio |
| Contratos backend | 31 API/reconciliación + 16 dominio + 11 plataforma/PostgreSQL, OK |
| Regresión web | 44/44 Chromium, OK |
| Accesibilidad | 27/27 Axe, OK |
| Aislamiento | puertos loopback y proyecto `fincilia-e2e` verificados |
| Limpieza | contenedores, redes y volúmenes desechables ausentes al terminar |
| Duración | 225,1 segundos |

La regresión cubrió identidad, alta de empresa, roles, carga CSV/XLSX/ODS,
documentos, mapeo, publicación, linaje, conciliación, expedientes, saldos,
pre-cierre, informes, recordatorios, calidad, facturación visible, plataforma,
shell público, rutas legales y límites de autorización.

El resultado amplía la confianza sintética, pero no cambia DRG-00, DRG-01 ni
GA-01. No se usaron archivos financieros reales ni proveedores externos y las
revisiones independientes continúan pendientes.
