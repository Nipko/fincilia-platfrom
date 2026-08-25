---
task_id: FNC-SEC-005
status: REVIEW_PENDING
base_sha: b506e93
implementation_sha: c9b3094
integration_sha: 4743412
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Database/Architecture]
---

# Handoff FNC-SEC-005

## Resultado entregado

Los trabajos nuevos de documentos conservan la capability persistente que los
autorizó. La API emite el contexto en la misma transacción que registra y encola
el artefacto; el scan propaga el mismo contexto a profile/extract. El protocolo
de despacho lo revalida antes de reclamar, dentro del lock de cada lote y antes
de cerrar con éxito.

## Integridad y privilegios

- V0022 agrega un FK compuesto `(company_id, issued_context_id)`; una capability
  de otra empresa no se puede adjuntar.
- `fincilia_app` sigue sin UPDATE de `processing_run` ni acceso a
  `dispatch_pointer`.
- `fincilia_worker` no recibe la clave HMAC, escritura de cola ni lectura directa
  de identidad. Solo presenta el contexto ya ligado por el productor a la puerta
  definer de despacho.
- `fincilia_dispatch` es no-login, sin DDL permanente. Lee la ruta mínima de
  autoridad para que estado, membership y grant también se revaliden aunque una
  escritura administrativa olvidara incrementar `authorization_version`.
- Un contexto expirado, revocado o desalineado termina el run con
  `authorization_context_invalid/requires_human`; nunca se publica como éxito.

## Evidencia ejecutada

- `python -m tools.migration_readiness.validate`: OK, V0001–V0022.
- `python -m tools.runtime_config.validate`: OK, 30 variables.
- 74 pruebas de migration readiness + runtime config: OK.
- 108 pruebas unitarias API: OK.
- 18 pruebas unitarias worker: OK.
- 5 pruebas PostgreSQL nuevas de vínculo/revocación/ACL: OK.
- 44 pruebas PostgreSQL de contextos, despacho y compatibilidad: OK.
- 26 pruebas HTTP/PostgreSQL; la subida real a MinIO demuestra
  `processing_run -> issued_authorization_context`: OK.
- Quality gate sobre el índice del commit productor: sin hallazgos.

## Hallazgos de ejecución

1. La suite nueva reclamaba trabajo legítimo ya existente en el stack. Ahora
   aparca y restaura exactamente los punteros ajenos; no los consume ni reordena.
2. La prueba HTTP falló correctamente con 503 cuando MinIO estaba detenido. Al
   levantar la dependencia declarada, el recorrido pasó sin cambiar la política.
3. `authorization_version` sola no demuestra autoridad viva si una ruta
   administrativa defectuosa cambia membership/engagement sin incrementarla. Por
   eso el despacho revalida ambos mecanismos y no solo el contador.

## Divergencias y trabajo posterior

- Expand-only: `issued_context_id` es nullable y la firma de tres argumentos se
  conserva para trabajos/binarios anteriores. Una tarea contract debe medir cero
  productores legacy, retirar la firma y aplicar `NOT NULL`.
- El modelo canónico describe `processing_run` financiero/evidencial, pero no
  modela referencias al plano de control. No se agregó una entidad de Access al
  catálogo financiero en silencio; Architecture debe decidir cómo expresar ese
  FK cross-plane.
- Exports, shared links y schedules aún no consumen la capability.
- Las funciones SECURITY DEFINER siguen `human_review_state: pending`; este
  handoff no cuenta como revisión independiente.

## Revisión requerida

Security debe revisar la lectura mínima concedida a `fincilia_dispatch`, los
dominios HMAC y las transiciones de revocación. Database/Architecture debe revisar
locks, orden de puntero/run, ACL reales y el plan expand-contract. El implementador
y `FOUNDER-01` no cuentan como revisores independientes.

## Rollback

No editar V0022 después de aplicada. Revertir la aplicación a `b506e93` sigue
siendo compatible porque la columna es nullable y las firmas antiguas sobreviven.
Corregir esquema mediante una migración forward-fix. No borrar contextos, runs ni
historial para deshacer.

## Rutas liberadas

`db/migrations/V0022__processing_run_authorization_context.sql`,
`db/tests/test_processing_authorization_context.py`, productor API, worker,
configuración local y documentos listados por FNC-SEC-005.
