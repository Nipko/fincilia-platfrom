---
id: FNC-WEB-004
title: Sistema visual y navegacion contextual de la plataforma web
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 83d2392
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accessibility/QA]
---

# Resultado esperado

La plataforma web presenta una jerarquia visual coherente y reconocible desde
el acceso hasta el trabajo por empresa. Las acciones se agrupan por intencion,
el contexto de empresa permanece visible, la informacion tecnica de acceso no
compite con el trabajo diario y las vistas principales son utilizables sin
desplazamiento horizontal accidental en escritorio o movil.

Es una rebanada exclusivamente de presentacion y navegacion sobre las rutas ya
autorizadas. No cambia reglas financieras, autorizacion, persistencia, API,
gates ni el alcance sintetico del entorno local.

# Dependencias

- FNC-WEB-003 y FNC-QA-010 en `review_pending` con evidencia automatizada.
- ADR-010 e `INFORMATION_ARCHITECTURE.md` como limites de la experiencia web.
- No requiere migracion, permiso nuevo, dependencia de frontend ni proveedor.

# Rutas permitidas

- `apps/web/src/app/**`
- `apps/web/src/components/**`
- `apps/web/e2e/**`
- `apps/web/src/**/__tests__/**`
- `docs/implementation/tasks/FNC-WEB-004.md`
- `docs/implementation/handoffs/FNC-WEB-004.md`
- registros centrales por Integration Steward.

# Rutas prohibidas

- API Python, base de datos, migraciones, workers e infraestructura.
- Autorizacion, RLS, SoD, contratos financieros y esquema canonico.
- Aplicacion movil, datos reales, conectores externos e IA.
- Aceptacion de gates o revisiones humanas.

# Criterios de aceptacion

- **AC-01.** Acceso, portafolio y vistas por empresa comparten marca, escala,
  espaciado, superficies, estados y controles consistentes.
- **AC-02.** La navegacion multiempresa y por empresa se agrupa por objetivo y
  conserva nombres/rutas accesibles existentes.
- **AC-03.** La portada de empresa prioriza carga, documentos y proximas
  acciones; roles y permisos tecnicos quedan disponibles como detalle
  secundario sin ocultarse.
- **AC-04.** Tablas, tarjetas, formularios, alertas y estados vacios tienen una
  jerarquia visual clara sin depender solo del color.
- **AC-05.** A 390 px no existe overflow horizontal de pagina en acceso,
  portafolio ni portada de empresa; tablas anchas conservan scroll local.
- **AC-06.** Focus visible, landmarks, nombres accesibles, contraste y
  `prefers-reduced-motion` se conservan o mejoran.
- **AC-07.** No se agrega una dependencia ni se cambia una decision server-side.
- **AC-08.** Unitarias, lint, tipos, build, E2E y Axe aplicables quedan verdes.

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

- AC-01..AC-08 tienen evidencia reproducible y capturas localmente verificadas.
- La regresion visual cubre escritorio y 390 px en Chromium.
- Revisores Product y Accessibility/QA quedan pendientes, no inventados.
- Estado final `review_pending`; rutas liberadas; S1-READY sin cambios.
