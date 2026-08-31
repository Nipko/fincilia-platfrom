---
id: FNC-UAT-002
title: Aceptación integral desechable desde esquema vacío
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: ba91e70
implementation_shas: [1f4f2d7, 2bc936a]
tested_sha: 2bc936a
gate: DRG-00/DRG-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [QA, Platform/SRE, Security]
---

# Resultado

Demostrar en un runtime desechable que una instalación recién migrada permite
registrar la primera identidad sintética y crear su espacio inicial antes de
ejecutar la regresión sembrada completa. Cada fase elimina sus recursos exactos
y nunca conecta, lee ni modifica `fincilia-local`.

# Autoridad y alcance

- ADR-033 mantiene UAT separado y prohíbe promover sus datos.
- FNC-QA-009 define el runtime local desechable y su limpieza fail-closed.
- Se corrige el contrato E2E de cierre para reflejar FNC-CLS-006 sin permitir
  cierre cuando el expediente no está apto.

# Rutas reservadas

- `infra/local/test-web-isolated.ps1`, `.sh` y `README.md`.
- `docs/platform/isolated-web-runtime.json`.
- `tools/isolated_web_runtime/**`.
- `apps/web/package.json` y pruebas E2E de alta/cierre.
- esta ficha, handoff y registros centrales por Integration Steward.

# Criterios de aceptación

1. Existe una fase `empty` cerrada que construye, migra y levanta sin seed.
2. El alta pública sintética crea identidad, firma y primera empresa desde cero.
3. El entorno vacío se elimina y demuestra ausencia antes de crear el sembrado.
4. Chromium y Axe completos se ejecutan después sobre una segunda base limpia.
5. Fallo en cualquier fase conserva cleanup en `finally` y no toca la demo.
6. El cierre bloqueado sigue sin presentar una acción de cerrar o certificar.
7. Dos ejecuciones limpias son la evidencia requerida; una sola no mueve gates.

# Fuera de alcance

Datos reales, UAT público, promoción a producción, aprobación de gates, cambios
de semántica financiera y operaciones destructivas sobre el runtime persistente.
