---
id: FNC-UAT-001
title: Ciclo UAT, promoción limpia y sanitización preproducción
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: 3fc23b4
implementation_shas: [65bc894, 7f95753, b099c64]
tested_sha: b099c64
gate: DRG-00/DRG-01
gate_effect: none
data_ceiling: current_gate_remains_authoritative
independent_reviewers: [Security, Privacy/Legal, Architecture, SRE, QA]
---

# Resultado

El dominio público de validación se presenta como UAT, se promueven artefactos
inmutables a un entorno de producción separado y existe una operación segura y
ensayada para retirar cuentas/datos de prueba sin confundirla con despliegue.

# Criterios de aceptación

1. La UI y documentación operativa vigente no llaman beta al entorno público.
2. UAT y producción no comparten base, buckets, secretos, claves ni backups.
3. La promoción referencia digest/release exactos y no copia datos de UAT.
4. La sanitización exige entorno UAT, preflight, respaldo, token de confirmación
   de corta vida, allowlist de tablas/buckets y evidencia posterior.
5. El superadmin bootstrap se conserva o reconfigura explícitamente; nunca nace
   un acceso accidental tras un reset.
6. La primera ejecución se ensaya con datos desechables antes de autorizarla en
   el entorno público.

# Fuera de alcance inmediato

- Ejecutar un reset ahora.
- Declarar producción o superar gates automáticamente.
- Copiar cuentas de prueba a producción.

# Ronda operativa R1

Base `3fc23b4`. El ensayo previo al reset endurece la frontera del corte: plan y
token con owner/modo verificados, cancelación autenticada, reanudación automática
ante fallos predestructivos y estado `recovery_required` sin reapertura si el
fallo ocurre después de reemplazar volúmenes o secretos. La ejecución pública
continúa deshabilitada y la restauración automática post-corte sigue pendiente
de un ensayo desechable.

# Ronda operativa R2

La publicación de una release ya no confía únicamente en el checksum del bundle:
valida las tres imágenes T0 por digest, los flags fail-closed y la configuración
invitation-only; exige backup y restore-check frescos; prueba el HTTPS público y
solo entonces escribe evidencia minimizada de despliegue. Un fallo de salud o de
persistencia de evidencia restaura el bundle anterior. La ejecución AWS queda
pendiente de CI verde y de una sesión temporal nueva; ningún recurso ni dato se
modifica desde esta ronda.

# Evidencia de integración R2

- CI `33473978646` sobre `b099c64`: políticas, migraciones PostgreSQL 17,
  RLS/worker, límites de autorización, ciclo local completo, Chromium y WCAG
  finalizaron en verde; el carril de rendimiento quedó omitido porque sólo se
  ejecuta bajo solicitud manual.
- candidato `33474841341` sobre el mismo SHA: imágenes API/worker/web construidas
  sin publicar, usuarios no-root comprobados, pruebas internas verdes, bundle
  reproducido dos veces, archivo verificado y attestations SLSA/SPDX firmadas y
  verificadas con la identidad OIDC del workflow.
- `tools.drg01_technical` conserva 90 casos adjudicados y cero errores. El
  evaluador de readiness sigue válido con 14 blockers y `real_data_authorized:
  false`; ninguna evidencia de esta ronda mueve DRG-00 ni DRG-01.

La siguiente operación es desplegar el candidato en UAT mediante una sesión AWS
temporal nueva y sólo después de obtener backup y restore-check frescos. El
deployer falla cerrado si falta cualquiera de esas condiciones.
