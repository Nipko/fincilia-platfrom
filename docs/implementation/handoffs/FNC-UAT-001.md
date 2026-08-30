---
id: FNC-UAT-001
status: IN_PROGRESS
base_sha: 501f65415182bed42494e66abe0ddac75ef38747
implementation_sha: 90f833fba83b876cd5a4b0a736876c85b9e0911d
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

## Pendiente para cerrar la tarea

1. Provisionar un entorno desechable que replique la topología UAT.
2. Ejecutar freeze, backup, restore drill, reemplazo, migración, bootstrap y
   smoke test con datos completamente sintéticos.
3. Persistir evidencia digest-only y demostrar que ningún objetivo de
   producción estuvo en el plan.
4. Obtener revisiones Security, Privacy/Legal, Architecture/Database, SRE y QA.
5. Solo después habilitar la operación para UAT público. No se ejecutó reset en
   este lote.

## Rollback

Antes de retirar el plano anterior, el DNS/runtime conserva su destino actual.
Si el nuevo plano falla, se descarta el nuevo plano y se mantiene el anterior.
Después del corte, la recuperación usa el backup verificado y mantiene sesiones
anteriores invalidadas. Nunca se restaura sobre producción.
