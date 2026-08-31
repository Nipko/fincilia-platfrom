---
id: FNC-GAT-006
title: Evidencia adjudicada de aislamiento, ingreso y canales DRG-01
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 161a983
gate: DRG-01
gate_effect: evidence_only
data_ceiling: synthetic_only_until_gate
independent_reviewers: [Security, Privacy, Database, Data, QA]
---

# Resultado

Un manifiesto reproducible liga pruebas ejecutadas contra PostgreSQL 17 y MinIO
con el código exacto que demuestra aislamiento entre empresas, cuarentena antes
de `raw` y ausencia de canales de ingreso no autorizados.

# Criterios de aceptación

1. Los selectores de prueba deben existir y su archivo queda ligado por SHA-256.
2. PAN, credenciales, contenido activo y formatos sin escáner nunca llegan a `raw`.
3. Empresa, RLS, revocación y contexto de autorización fallan cerrados.
4. Email ingest, SFTP, conectores y webhooks no tienen ruta; IA y pagos siguen apagados.
5. CI repite la suite PostgreSQL antes de validar el manifiesto.
6. La evidencia no autoriza datos reales ni cubre identidad runtime, cloud, restore,
   derechos, incidente, cadena de suministro o revisión humana.

# Rutas

- `tools/drg01_technical/**`
- `docs/implementation/evidence/FNC-GAT-006.json`
- `docs/security/drg01-readiness.json` y su validador
- CI, fase vigente y handoff

# Verificación

```text
python -m unittest tools.drg01_technical.test_model tools.drg01_readiness.test_validate -v
python -m tools.drg01_technical.cli
python -m tools.drg01_readiness.validate
```
