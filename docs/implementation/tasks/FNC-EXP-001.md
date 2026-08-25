---
id: FNC-EXP-001
alias: FNC-P4.9
title: Exportacion canonica segura de dataset publicado
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: c1f074d0c4775e6f2b37d55f8105fdad610d2378
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Backend/Architecture, Product/Accounting, Accessibility/QA]
---

# Resultado esperado

Una persona autorizada puede descargar un CSV canonico, estable y legible de un
dataset ya publicado. La descarga sirve como salida operativa del limpiador: no
incluye basura del documento original, no aplica correcciones pendientes y no se
presenta como informe certificado, conciliacion de saldos ni cierre.

# Autoridad y limites

- `dataset_version` y `canonical_movement` publicados son la unica fuente de la
  exportacion; el navegador nunca aporta filas, empresa, conteos ni estado.
- Se introduce `dataset.export` como permiso distinto de lectura paginada y de
  `portability.export`. Solo `owner`, `preparer`, `reviewer` y `auditor` lo
  reciben en el prototipo local; Security debe revisarlo antes de datos reales.
- El endpoint permanece bloqueado si `real_data_enabled=true`. Esta tarea no
  mueve DRG-00, S1-READY ni habilita egress productivo.
- No se persiste una copia: el CSV se transmite bajo demanda y `no-store`, para
  no crear otra retencion ni una nueva fuente de verdad.

# Definition of Ready

- Base declarada integrada, arbol limpio y CI verde.
- Dataset publicado, movimientos inmutables y linaje reproducible disponibles.
- Integration Steward reserva contratos, API, web, pruebas y registros.
- No se requieren migraciones, object storage, IA, conectores, movil ni datos
  reales.

# Rutas permitidas

- `packages/contracts/python/fincilia_contracts/tenancy.py` y sus pruebas.
- `docs/security/RBAC_ABAC_SOD.md` para distinguir exportacion operativa de
  portabilidad privilegiada, sin aceptar el documento.
- `apps/api/src/fincilia_api/exports.py`, `routes.py` y pruebas API/PostgreSQL.
- `apps/web/src/**` y `apps/web/tests/**` para BFF, UI, unitarias, E2E y Axe.
- Ficha, handoff y registros centrales por Integration Steward.

# Rutas prohibidas

- Migraciones, mutacion del dataset, overlays aplicados al vuelo o archivos
  persistidos en la zona `exports`.
- Datasets `staging`, `validated`, `rejected`, incompletos, con linaje no completo
  o manifiesto no reproducible.
- Informes certificados, saldos, cierre, auto-match, tolerancias o fraude.
- Datos reales, IA, conectores, movil, secretos y ADR Accepted.

# Criterios de aceptacion

- **AC-01.** Solo un dataset publicado, completo, con linaje completo y manifiesto
  reproducible puede exportarse; cualquier otro estado falla cerrado.
- **AC-02.** La API exige `dataset.export`, resuelve `company_context` en servidor
  y lee dentro de RLS. Acceso cross-company o permiso ausente es neutral.
- **AC-03.** El CSV tiene columnas cerradas, orden por `record_ordinal`, fechas
  ISO y dinero decimal de 12 posiciones; dos descargas producen bytes identicos.
- **AC-04.** Descripcion y referencia neutralizan formula injection sin alterar
  columnas numericas. CR/LF, comillas, Unicode y valores nulos son validos.
- **AC-05.** La generacion usa cursor por lotes, no materializa el dataset entero,
  emite nombre seguro, `no-store`, `nosniff` y audita solo actor, dataset, filas,
  formato y resultado, nunca valores.
- **AC-06.** El BFF web transmite bytes y cabeceras allowlisted sin exponer token,
  cuerpo de error interno ni cachear la respuesta.
- **AC-07.** La UI muestra la descarga solo con permiso y estado elegible, y la
  rotula como exportacion canonica no certificada, sin prometer conciliacion.
- **AC-08.** Unitarias de contrato/API/web, PostgreSQL cross-company, E2E de
  descarga, Axe, lint, tipos, build, quality gate, handoff y CI pasan.

# Rollout y rollback

Solo entorno local sintetico. Rollback elimina permiso, endpoint, BFF y enlace;
no hay migracion, archivo retenido ni dato financiero que revertir.

# Definition of Done

- AC-01..AC-08 con evidencia reproducible y commits incrementales.
- Revision humana pendiente declarada; ningun gate o ADR cambia de estado.
- Rutas liberadas, handoff `REVIEW_PENDING` y CI verde.
