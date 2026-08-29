---
id: FNC-SUP-002
title: Attestation verificable del candidato de release
epic: FNC-EP-PLATFORM
phase: F0
iteration: E1
type: implementation
status: review_pending
priority: P0
accountable_owner: FOUNDER-01
agent_lane: Platform/SRE
implementer: Codex principal dev + Integration Steward
independent_reviewer: Security + QA
plan_refs: [29, 32, 36, 54]
adr_refs: [ADR-001, ADR-020, ADR-023]
dependencies: [FNC-SUP-001, FNC-REL-001]
gate: DRG-00
gate_effect: evidence_only
allowed_data: synthetic_only
security_impact: high
privacy_impact: low
risk_ids: [TM-005]
---

# Resultado esperado

El workflow manual produce un archivo determinista del candidato, genera una
attestation SLSA de procedencia y una attestation SPDX firmadas mediante la
identidad OIDC del workflow, y verifica ambos bundles Sigstore contra el
repositorio, el workflow firmante y el commit exacto.

La evidencia reduce los gaps técnicos de SBOM, firma y procedencia, pero no
autoriza producción ni datos reales. La equivalencia de los SHA de actions con
sus tags y la revisión de Security siguen siendo independientes.

# Base y alcance

- Base de reserva: `0c148e66d0ad27860ab23d752f3a5a40ce63ecaf`.
- Datos autorizados: únicamente sintéticos.
- Rutas permitidas: `tools/release_candidate/**`,
  `docs/platform/release-candidate.json`,
  `docs/platform/RELEASE_CANDIDATE.md`,
  `.github/workflows/release-candidate.yml`,
  `docs/security/supply-chain.json`, `tools/supply_chain/**`, esta ficha, su
  handoff, `tools/quality_gate/**`, `docs/testing/CI_QUALITY_GATE.md` y registros
  centrales modificados por el Integration Steward.
- Rutas prohibidas: producto, migraciones, secretos, configuración AWS,
  identidad, autorización financiera y estados humanos.

# Criterios de aceptación

1. El archivo contiene exactamente el bundle validado, con orden, metadatos y
   compresión deterministas; traversal, links, extras y tamper fallan cerrados.
2. El SBOM agregado SPDX 2.3 liga los tres inventarios al commit y queda ligado
   por digest al manifiesto del candidato.
3. `actions/attest` está fijada a SHA completo y usa sólo
   `id-token: write`, `attestations: write` y `contents: read`.
4. Procedencia y SBOM se verifican con `gh attestation verify`, exigiendo
   repositorio, workflow firmante, commit fuente y runner hospedado.
5. La evidencia y sus URL/digests quedan en un handoff reproducible; claims no
   demostrados permanecen pendientes.
6. Unitarias, supply-chain, quality gate y CI aplicables pasan.

# Fuera de alcance

- Publicar o promover imágenes, elegir registry/KMS o habilitar producción.
- Marcar DRG-00, DRG-01 o TM-005 como cerrados.
- Declarar revisión independiente o equivalencia de tags sin la persona que la
  realizó.

# Rollback

Retirar los dos pasos de attestation y descartar el candidato. No hay migración,
datos ni runtime persistente.

# Evidencia obtenida

- Workflow `33256843904`, SHA fuente
  `1aa44c29af51709e7f675cdeee76c453fc30f416`, conclusión `success`.
- Sujeto `fincilia-release.tar.gz` con SHA-256
  `81b87a7d161f002bc74acf08c3b26ab2009bfcaa8870d5a7f5c538817560d32e`.
- Predicados verificados dentro y fuera del runner:
  `https://slsa.dev/provenance/v1` y `https://spdx.dev/Document/v2.3`.
- 27 pruebas de release, 80 de supply-chain y 10 de política focales verdes.
- SBOM/firma/procedencia pasan; origen independiente de Actions sigue pendiente.
