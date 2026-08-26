---
task: FNC-DQ-001
status: REVIEW_PENDING
base_sha: 0ac623c
implementation_commits: [47fd260, 9e5bc04, 3d604e1, 317b0eb]
data_ceiling: synthetic_only
reviewers_pending: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Resultado

Centro multiempresa de calidad con ocho reglas deterministas versionadas, RLS,
permisos de lectura/gestion, escaneo idempotente y acotado, triaje auditado y
eventos append-only. La respuesta no copia importes, referencias, descripciones
ni fingerprints y declara efecto financiero nulo y ausencia de afirmacion de
fraude.

# Evidencia ejecutada

- Contratos Python: 30 pruebas OK.
- API unitaria: 102 pruebas OK.
- PostgreSQL + MinIO: 2 recorridos, RLS, permisos, replay y transiciones OK.
- Migracion V0018: blank aplicada y replay `mutated: false`, head V0018.
- Web: typecheck y lint OK; 151 pruebas unitarias OK; build Next OK.
- Navegador: 2 E2E chromium OK y 1 axe/WCAG automatizado OK.
- `tools.work_graph.validate` y `tools.quality_gate.cli`: OK.

# Limites conservados

Solo datos sinteticos. El escaneo toma como maximo 100 datasets recientes y 500
hallazgos por regla, informa truncamiento y no resuelve automaticamente una
alerta que deja de observar. Ninguna alerta alimenta publicacion, auto-match,
cierre o reporte certificado. No se uso IA.

# Revision requerida

Product/Accounting revisa reglas y lenguaje; Security revisa RLS, auditoria y
ausencia de valores crudos; Backend/Architecture revisa consultas y limites;
Accessibility/QA revisa el flujo visual. Esto no acepta ADR-002, S1-READY ni un
data gate. V0018 se ejercio solo bajo `migration-tooling.local_build`.

# Rollback

Revertir consumidores web, luego API/contrato. V0018 es forward-only: una base
que ya la aplico requiere migracion compensatoria y nunca editar su checksum.
