---
task_id: FNC-ACC-001
status: REVIEW_PENDING
base_sha: a1f03c7430e30c15ccf0a3ed411c3baf7d4e26bb
implementation_shas: [443450f]
tested_head_sha: 4eed9d5
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Accounting, Product, Architecture, Accessibility/QA]
---

# Handoff FNC-ACC-001 — flujo contable guiado de punta a punta

## Resultado integrado

Cada empresa tiene una estación `/flujo-contable` que organiza en siete pasos
las capacidades existentes: cuentas/fuentes, ingreso e inspección, limpieza y
publicación, conciliación, saldos, expediente previo al cierre e informes. Cada
paso muestra evidencia obtenida por API, su estado y una siguiente acción hacia
la estación productiva ya existente.

La derivación es pura y distingue `available`, `restricted` y `unavailable`.
Una denegación jamás se convierte en cero; cuarentena, parcial, desconocido o no
verificado no se presentan como completitud. Confirmar candidatos continúa sin
efecto financiero y preparar el expediente no ejecuta ni certifica el cierre.

## Evidencia

- 3 pruebas unitarias cubren recorrido vacío, avance y fail-closed por permiso.
- Chromium verificó siete etapas, límites y acciones sobre PostgreSQL/MinIO
  sintéticos; la variante 390×844 no tiene overflow global.
- Axe no encontró hallazgos serios o críticos en la estación.
- El conjunto web pasó 249 pruebas, lint, TypeScript y build de producción.
- La regresión desechable confirmó 33 recorridos antiguos y los 3 nuevos; 8
  helpers antiguos no pudieron alcanzar el puerto API desde Windows/WSL
  (`ECONNREFUSED`) pese a salud interna. No hubo fallo de UI y el proyecto
  `fincilia-e2e` fue eliminado con volúmenes y redes verificados. CI Linux debe
  consolidar la regresión completa sobre el commit entregado.

## Límites y revisión requerida

No se cambiaron ecuaciones, matching, dinero, linaje, RLS, SoD ni migraciones.
La vista es un orquestador de lectura y navegación; no prueba que un periodo sea
contablemente correcto. Accounting debe revisar lenguaje y orden; Architecture,
composición de lecturas; Product y Accessibility/QA, recorrido y accesibilidad.
S1-READY y el techo sintético no cambian.

## Rollback

Revertir `443450f` retira el modelo, la página y su enlace contextual. Ninguna
evidencia, decisión, movimiento o estado financiero se modifica. Las rutas
quedan liberadas con este handoff.
