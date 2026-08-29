---
id: FNC-UX-003
title: Shell SaaS premium y sistema visual web v2
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: a1f03c7430e30c15ccf0a3ed411c3baf7d4e26bb
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product/UX, Accessibility/QA]
---

# Resultado

La plataforma autenticada usa un shell SaaS profesional con navegacion
jerarquica, contexto de cuenta, superficies y estados consistentes. La portada
publica y el acceso comparten la misma identidad visual sin ocultar que se trata
de una beta.

# Rutas

- `apps/web/src/app/**`, `apps/web/src/components/**` y pruebas web.
- Sin dependencias nuevas, API, migraciones, workers ni semantica financiera.
- Ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptacion

1. Navegacion autenticada separa Operacion, Control y Administracion con estado
   actual visible y acceso directo a Cuenta.
2. Escritorio usa una jerarquia estable; movil ofrece menu compacto sin overflow
   global ni interacciones exclusivas de hover.
3. Tokens de color, tipografia, espacio, radio, sombra, tablas, formularios,
   botones, metricas, alerts y skeletons forman un sistema coherente.
4. Motion acompana entrada, feedback y jerarquia sin bloquear interaccion; con
   `prefers-reduced-motion` queda desactivado.
5. Focus, contraste, targets, landmarks y estados no dependen solo del color.
6. No se agrega dependencia ni se expone token, permiso o topologia al cliente.
7. Lint, tipos, build, Chromium, responsive y Axe quedan verdes.

# Fuera de alcance

Aplicacion movil, branding juridicamente aprobado, animaciones canvas/WebGL,
telemetria externa, cambio de autorizacion o aceptacion de gates.
