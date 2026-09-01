---
id: FNC-UAT-001
status: IN_PROGRESS
base_sha: 501f65415182bed42494e66abe0ddac75ef38747
implementation_sha: b099c64efba1307ae2d93cf438be441f60003928
integration_sha: 9ba610f75f327967382653c7306cc0f36f7ecc6e
data_ceiling: current_gate_remains_authoritative
---

# Handoff parcial FNC-UAT-001 — UAT y producción limpia

## Resultado integrado

ADR-033, el contrato `uat-lifecycle.json`, su validador y el runbook fijan una
frontera inequívoca:

- `fincilia.com` es la superficie UAT actual;
- producción aún no está provisionada;
- se promueve un artefacto inmutable, no cuentas, objetos ni base UAT;
- producción tendrá PostgreSQL, buckets, Valkey, KMS, secretos, identidad,
  backups y auditoría separados;
- limpiar UAT significa reemplazar su plano de datos, no truncar tablas ni
  exponer un botón web.

## Evidencia

`python -m tools.uat_lifecycle.validate` devuelve `ok: true`. Doce pruebas de
mutación demuestran que el contrato rechaza compartir estado, convertir UAT en
producción, copiar cuentas/base, reset in-place, botón web, token de más de 15
minutos, ausencia de restore drill, copia del superadmin o activación prematura.

La ronda R2 añade evidencia ejecutada sobre
`b099c64efba1307ae2d93cf438be441f60003928`:

- CI `33473978646`, completo y verde, incluido PostgreSQL real, Chromium y WCAG;
- candidato no publicado `33474841341`, completo y verde;
- bundle determinista, SBOM SPDX y procedencia SLSA firmados por OIDC y
  verificados contra fuente, ref y workflow exactos;
- validador técnico DRG-01 con 90 casos, cero errores y el techo sintético
  intacto;
- readiness válido, 14 blockers visibles y datos reales no autorizados.

El despliegue quedó endurecido para aceptar sólo imágenes T0 por digest, flags
de UAT sintético cerrados, backup menor de 26 horas y restore-check menor de
ocho días. Después de reiniciar exige HTTPS público sano y persiste evidencia
minimizada en `deployment-evidence/uat/<sha>/`; cualquier fallo restaura el
bundle anterior.

## Pendiente para cerrar la tarea

1. Renovar la sesión temporal AWS y comprobar cuenta/región antes de cualquier
   plan o escritura.
2. Crear backup y restore-check frescos, publicar las tres imágenes T0 por
   digest y aplicar únicamente el delta del bundle de la release.
3. Ejecutar el despliegue in-place y conservar su evidencia; no ejecutar el
   reset público, que continúa deshabilitado hasta ensayo desechable y revisión.
4. Ensayar freeze, reemplazo, migración, bootstrap y recuperación en una
   topología desechable con datos completamente sintéticos.
5. Obtener revisiones Security, Privacy/Legal, Architecture/Database, SRE y QA.

## Rollback

Antes de retirar el plano anterior, el DNS/runtime conserva su destino actual.
Si el nuevo plano falla, se descarta el nuevo plano y se mantiene el anterior.
Después del corte, la recuperación usa el backup verificado y mantiene sesiones
anteriores invalidadas. Nunca se restaura sobre producción.
