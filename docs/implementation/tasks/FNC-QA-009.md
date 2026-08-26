---
id: FNC-QA-009
title: Regresion web aislada de la demo persistente
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 8846157
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [QA, Platform/SRE, Security]
---

# Resultado

Ejecutar Chromium y Axe sobre un proyecto Compose desechable que no comparte
puertos, redes ni volumenes con `fincilia-local`. Cada corrida parte de una base
sintetica nueva y elimina exclusivamente sus recursos al terminar, incluso ante
fallo, de modo que la regresion automatizada no contamine la demo persistente.

# Definition of Ready

- FNC-QA-008 y FNC-PLT-009 estan integradas y en revision.
- La suite completa es repetible, pero sus altas append-only se conservan hoy en
  el mismo runtime que usa el fundador para pruebas manuales.
- Compose admite nombres de volumen explicitos y puertos web/API alternativos.
- Arbol limpio y datos exclusivamente sinteticos locales.

# Rutas reservadas

- `infra/local/compose.yaml`.
- `infra/local/fincilia-local.ps1`.
- `infra/local/test-web-isolated.sh`.
- `infra/local/test-web-isolated.ps1`.
- `infra/local/scripts/e2e_fixture.py`.
- `infra/local/README.md`.
- `apps/web/tests/e2e/quality-center.spec.ts`.
- `apps/web/tests/e2e/close-readiness.spec.ts`.
- `docs/platform/isolated-web-runtime.json`.
- `tools/isolated_web_runtime/**`.
- `.github/workflows/ci.yml` (solo lanes de contrato).
- Esta ficha, su handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- `apps/api/**`, `apps/web/src/**`, `db/**`, migraciones y la semilla de demo.
- Borrar o recrear volumenes, redes o contenedores de `fincilia-local`.
- Aceptar datos reales, alterar RLS/SoD/auditoria o fabricar aprobaciones.
- Mobile, IA, proveedores externos, gates o ADR aceptados.

# Criterios de aceptacion

- **AC-01.** El proyecto desechable, sus dos volumenes y sus dos redes tienen
  nombres cerrados distintos de los persistentes; todos los puertos publicados
  siguen ligados a `127.0.0.1` y no colisionan con 53000/58080/59000/59001.
- **AC-02.** El lifecycle valida sus constantes antes de cualquier `down
  --volumes`; nunca acepta un nombre de proyecto, volumen, red o compose file
  proporcionado por el usuario.
- **AC-03.** La secuencia construye, migra, siembra solo sinteticamente, levanta,
  comprueba readiness y despues ejecuta Chromium y Axe contra la URL aislada.
- **AC-04.** Un bloque `finally`/`trap` elimina solo el proyecto desechable y sus
  volumenes aun si arranque o pruebas fallan.
- **AC-05.** Dos corridas consecutivas completas pasan y tras cada una no queda
  ningun contenedor, red ni volumen del proyecto desechable.
- **AC-06.** La identidad y el estado observable de `fincilia-local` son iguales
  antes y despues; sus volumenes nunca aparecen como objetivo destructivo.
- **AC-07.** Un contrato ejecutable y mutaciones adversariales detectan project
  drift, volumen/red compartidos, puertos persistentes, falta de cleanup,
  ausencia de readiness o una suite omitida.

# Limites y rollback

La tarea cambia solo infraestructura local de pruebas. El camino persistente
conserva sus defaults y semantica no destructiva. El rollback elimina el runner,
su contrato y los overrides parametrizados; nunca toca datos. La revision
independiente de QA, Platform/SRE y Security permanece pendiente.
