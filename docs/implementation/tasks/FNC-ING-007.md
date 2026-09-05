---
id: FNC-ING-007
title: OCR local aislado para PDF escaneado
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: ea3c938
implementation_sha: e4e7dfd
gate: DRG-00/DRG-01
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Security, Privacy, Data, Architecture, QA]
---

# Resultado esperado

Completar el recorrido de PDF escaneado con un motor OCR local, reproducible y
sin egress. El worker valida primero la envolvente PDF, renderiza dentro de
límites cerrados, inspecciona todo el texto reconocido antes de promover y
conserva un derivado direccionado por contenido con localizadores por bloque.

# Rutas reservadas

- `packages/contracts/python/fincilia_contracts/pdf_document.py`
- `packages/contracts/python/fincilia_contracts/ingestion.py`
- `packages/contracts/python/tests/**`
- `workers/document/**`
- `packages/platform/python/fincilia_platform/settings.py`
- `packages/platform/python/tests/**`
- `db/migrations/V0062__local_pdf_ocr.sql`
- `db/migrations/V0063__pdf_ocr_migrator_maintenance.sql`
- `db/tests/test_pdf_ocr.py`
- `docs/database/migration-tooling.json`
- `infra/local/compose.yaml`
- `.github/workflows/ci.yml`
- `.env.example`
- `docs/platform/runtime-config.json`
- `apps/web/src/app/empresas/[companyId]/**`
- `apps/web/src/lib/**`
- `apps/web/tests/e2e/**`
- `docs/ingestion/PDF_OCR_WORKSPACE.md`
- esta ficha y su handoff
- registros centrales por Integration Steward

# Criterios de aceptacion

1. PDF activo, cifrado, ambiguo o fuera de límites se rechaza antes de renderizar.
2. OCR local tiene máximos explícitos de páginas, píxeles, bloques y tiempo.
3. El texto OCR completo pasa el escáner de secretos antes de promoción.
4. El texto no vive en PostgreSQL, logs, auditoría ni resultado del job.
5. El derivado es determinista, direccionado por SHA-256 y ligado al artefacto,
   versión OCR, página, bloque, caja y confianza.
6. `raw_record` distingue `pdf_text` de `pdf_ocr` y ambos exigen revisión humana.
7. El worker continúa sin red externa; el proveedor externo permanece ausente.
8. Unitarias, migración, PostgreSQL, worker, web, E2E y accesibilidad pasan.

# Límites

Solo datos sintéticos. No mueve DRG-00/01, no publica movimientos, no acepta
ADR-036 y no transmite documentos a IA ni a un proveedor OCR.

# Estado de entrega

Los ocho criterios tienen evidencia y el handoff reproducible está disponible.
La tarea queda en `review_pending` hasta revisión independiente y CI del commit
integrado; no se declara `done` ni se mueve ningún gate.
