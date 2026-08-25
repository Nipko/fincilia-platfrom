---
id: FNC-RPT-001
title: Centro web de informes operativos e historicos
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 1211f17
tested_head_sha: a18afcf
implementation_commits: [daf852a, 3bb4ec8, 5df883c, 5aa913a, f7c637d, a18afcf]
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accounting, Security, Accessibility/QA]
---

# Resultado esperado

El contador consulta por empresa un informe historico de documentos, datasets,
movimientos, conciliaciones y calidad. Los importes se presentan por moneda con
decimal exacto y nunca se consolidan entre empresas o monedas. Puede descargar
la misma serie mensual como CSV determinista.

Es un informe operativo sintetico y no certificado. No calcula saldos, no cierra
periodos, no confirma conciliaciones y no habilita datos reales.

# Rutas permitidas

- `apps/api/src/fincilia_api/reports.py`
- `apps/api/src/fincilia_api/routes.py`
- `apps/api/src/fincilia_api/access.py`
- `packages/contracts/python/fincilia_contracts/tenancy.py`
- `packages/contracts/python/tests/test_contracts.py`
- pruebas API y PostgreSQL de informes/autorizacion
- `apps/web/src/app/informes/**`
- `apps/web/src/app/api/companies/[companyId]/reports/**`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/reports.ts`
- `apps/web/src/app/empresas/page.tsx`
- `apps/web/src/app/empresas/[companyId]/page.tsx`
- `apps/web/src/app/globals.css`
- pruebas web y CI necesarias para el recorrido
- ficha, handoff, backlog, fase y reserva por Integration Steward

# Criterios de aceptacion

- **AC-01.** La API exige contexto server-side y `report.read`; RLS impide leer
  otra empresa y una revocacion no se interpreta como reporte vacio.
- **AC-02.** Rango explicito de 30, 90, 180 o 365 dias, inclusivo y basado en UTC.
- **AC-03.** Resumen de documentos, datasets, filas, movimientos, calidad y
  conciliacion con conteos completos, no muestras silenciosas.
- **AC-04.** Serie mensual de movimientos por moneda y direccion usa
  `numeric(38,12)` y devuelve cadenas decimales; nunca float.
- **AC-05.** Estados parciales, desconocidos, rechazados e invalidados quedan
  visibles y no alimentan una declaracion de completitud.
- **AC-06.** CSV determinista reproduce el mismo rango y orden; evita formulas,
  mezcla de empresas y contenido no confiable.
- **AC-07.** La web permite cambiar empresa y rango, muestra tendencias visuales
  accesibles, tabla equivalente y enlaces a evidencia.
- **AC-08.** La vista multiempresa carga company-by-company con concurrencia
  acotada y nunca suma importes entre empresas.
- **AC-09.** Auditoria registra metadatos de lectura/exportacion, no importes,
  referencias ni nombres de archivos.
- **AC-10.** Unitarias, PostgreSQL real, E2E, a11y, lint, tipos, build y CI pasan.

# Limites

- Sin migracion ni nueva proyeccion analitica.
- Sin informe certificado, balance, cierre, IA, conectores o datos reales.
- S1-READY y decisiones humanas permanecen sin aceptar.

# Evidencia entregada

API, contrato, PostgreSQL real, web, exportacion, E2E y accesibilidad estan
implementados y verificados en `a18afcf`. El handoff reproducible vive en
`docs/implementation/handoffs/FNC-RPT-001.md`. La tarea queda en revision
pendiente porque Product/Accounting, Security, Backend/Architecture y
Accessibility/QA deben revisarla de forma independiente; no modifica S1-READY.
