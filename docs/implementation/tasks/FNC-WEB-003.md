---
id: FNC-WEB-003
alias: FNC-P4.3
title: Portafolio multiempresa e historico operativo web
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 5565010
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accounting, Security, Accessibility/QA]
---

# Resultado esperado

El contador que opera varias empresas obtiene un portafolio visual con carga de
trabajo, vencimientos y estados de preparacion sin confundir falta de permiso con
cero actividad. Dentro de un documento puede navegar sus versiones historicas de
dataset sin que un identificador de URL salte a otra empresa o artefacto.

Es un prototipo local sintetico. No calcula saldos, no concilia, no certifica,
no crea auto-match y no habilita datos reales ni aplicacion movil.

# Dependencias

- FNC-WEB-001, FNC-WEB-002 y FNC-API-001 en `review_pending` con evidencia verde.
- Endpoints existentes de empresa, documentos, datasets y expectativas.
- No requiere migracion, permiso nuevo, cache ni proyeccion analitica.

# Rutas permitidas

- `apps/web/src/app/empresas/page.tsx`
- `apps/web/src/app/empresas/[companyId]/page.tsx`
- `apps/web/src/app/empresas/[companyId]/documentos/[artifactId]/mapeo/**`
- `apps/web/src/app/empresas/**/__tests__/**`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/navigation.ts`
- `apps/web/src/lib/portfolio.ts`
- `apps/web/src/lib/__tests__/navigation.test.ts`
- `apps/web/src/lib/__tests__/portfolio.test.ts`
- `apps/web/src/app/globals.css`
- ficha, handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- API Python, base de datos, migraciones, permisos, RLS, workers e infraestructura.
- Mobile, conectores, IA, reportes certificados, conciliacion y cierre.
- ADR, contratos compartidos y gates.

# Criterios de aceptacion

- **AC-01.** El portafolio carga empresas con concurrencia acotada y no bloquea
  todo si una empresa queda revocada durante la lectura.
- **AC-02.** Por empresa muestra conteos de documentos, datasets en revision,
  preparaciones parciales y expectativas vencidas/proximas cuando el servidor
  concede los permisos correspondientes.
- **AC-03.** Permiso ausente o 403 se presenta como `sin acceso`, nunca como cero.
- **AC-04.** Los conteos son operativos; no suman dinero ni infieren completitud,
  fraude, conciliacion o salud financiera.
- **AC-05.** La vista de empresa resume volumen y vencimientos con enlaces a la
  evidencia existente, sin duplicar reglas de autorizacion.
- **AC-06.** La vista de mapeo permite seleccionar una version de dataset de la
  lista autorizada y conserva ese contexto en paginacion y navegacion.
- **AC-07.** Un dataset solicitado que no pertenece al artefacto se rechaza de
  forma neutral; nunca se sustituye silenciosamente por otra version.
- **AC-08.** Una version historica publicada o rechazada es solo lectura; las
  acciones mutables se muestran segun el estado y permiso server-side.
- **AC-09.** Estados vacio, parcial y restringido son distinguibles y accesibles.
- **AC-10.** Unitarias, lint, tipos y build pasan; ninguna ruta prohibida cambia.

# Verificacion

```bash
cd apps/web
npm run lint
npm run typecheck
npm run test:unit
npm run build
cd ../..
python -B -m tools.work_graph.validate
python -B -m tools.test_catalog.cli validate
python -B -m tools.quality_gate.cli
```

# Definition of Done

- AC-01..AC-10 tienen evidencia y handoff reproducible.
- Revisores humanos quedan pendientes, no inventados.
- Estado final `review_pending`; rutas liberadas; S1-READY sin cambios.
