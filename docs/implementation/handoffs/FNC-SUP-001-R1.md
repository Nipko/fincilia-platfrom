---
task: FNC-SUP-001
status: REVIEW_PENDING
base_sha: d53bd7f
implementer: Integration Steward
data_ceiling: synthetic_only
gate: DRG-00
---

# Handoff FNC-SUP-001-R1

## Resultado

- Dependabot vigila todos los alcances npm, pip, Docker y GitHub Actions descubiertos.
- `.next` queda excluido como caché generada mediante el contrato ejecutable.
- `validate --gate <gate>` falla cerrado ante gates desconocidos y nunca oculta
  hallazgos de otros gates.
- S1 usa `validate --gate S1-READY`: queda verde porque los cuatro gaps existentes
  pertenecen a DRG-00.

## Evidencia

`python -m unittest tools.supply_chain.test_validate` ejecuta 76 pruebas verdes.
`validate --gate S1-READY` devuelve 0, muestra cuatro findings fuera de scope y
declara `out_of_scope_blocking_findings: 4`. `validate` sin scope continúa devolviendo
1. S1 queda con un blocker humano, no con cero.

## Límites

No existe todavía SBOM, firma, attestation ni verificación independiente de los SHA
upstream. TM-005 y DRG-00 siguen abiertos. Ninguna persona fue inventada como revisor.
