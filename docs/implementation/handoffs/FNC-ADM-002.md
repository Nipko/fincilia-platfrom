---
task_id: FNC-ADM-002
status: REVIEW_PENDING
base_sha: ba91e70
implementation_sha: 8e7dbaf
tested_sha: 2bc936a
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Database/Architecture, Platform/SRE, Privacy]
---

# Handoff FNC-ADM-002 — diagnostico operativo agregado

## Resultado

La consola `/plataforma` muestra al superadmin conteos operativos agregados de
trabajos, evidencia, dead letters, notificaciones y suscripciones. La fuente es
`fincilia.platform_operational_diagnostics()` de V0052, una funcion
`SECURITY DEFINER` que valida el rol de plataforma dentro de PostgreSQL y devuelve
un JSON cerrado. La API expone el resultado en `/api/v1/platform/diagnostics` y
la UI distingue datos disponibles, cero y degradacion.

La respuesta excluye nombres, identificadores de empresa/persona/documento,
archivos, importes, monedas, errores, payloads y filas individuales. La API no
acepta `company_id` ni obtiene acceso transversal a datos financieros.

## Controles y evidencia

- V0052 revoca ejecucion a `PUBLIC` y comprueba el rol de plataforma en base.
- pruebas de ACL demuestran denegacion a roles no autorizados.
- pruebas PostgreSQL ejercen funcion, respuesta agregada y endpoint autenticado.
- pruebas API validan que el adaptador solo retorna `operations`.
- tres pruebas focales web cubren tarjetas, ceros y estado indisponible.
- nueve pruebas PostgreSQL focales y la regresion UAT completa pasaron dos veces
  sobre `2bc936a`.

## Limites, revision y rollback

No hay break-glass, inspeccion de documentos, busqueda de usuarios, soporte
cross-company, edicion de roles ni metricas con cardinalidad sensible. Security
debe revisar la superficie definer; Database/Architecture ownership, ACL y RLS;
Platform/SRE utilidad operativa; Privacy el conjunto agregado. No hay revision
independiente aceptada.

Revertir `8e7dbaf` retira consumidores y V0052 solo mediante una migracion nueva;
una migracion ya aplicada nunca se reescribe ni elimina del historial.

## Rutas liberadas

V0052, pruebas PostgreSQL de plataforma, adaptador/ruta API, cliente/pagina/pruebas
web, ficha, handoff y registros centrales.
