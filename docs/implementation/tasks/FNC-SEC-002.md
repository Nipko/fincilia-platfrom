---
task: FNC-SEC-002
title: Threat model ejecutable y pruebas por riesgo alto
status: review_pending
implementer: Integration Steward
base_sha: 0bb360e
gate: S1-READY
data_ceiling: synthetic_only
---

# Resultado esperado

Convertir las amenazas del DFD y el seed de seguridad en escenarios de riesgo trazables. Cada riesgo debe declarar activo, flujo, categoría, precondición, abuso, impacto, score inherente, controles, pruebas, score residual proyectado, tratamiento, owner de rol, gate y aceptación humana pendiente.

## Rutas permitidas

- `docs/security/THREAT_MODEL.md`
- `docs/security/threat-model.json`
- `tools/threat_model/**`
- `docs/implementation/handoffs/FNC-SEC-002.md`
- `.github/workflows/ci.yml`
- `docs/testing/CI_QUALITY_GATE.md`
- `docs/architecture/C4.md` (solo estado de FNC-SEC-002)
- `CURRENT_PHASE.md`
- `docs/implementation/BACKLOG_PHASE_0.md`

## Criterios de aceptación

1. Todas las amenazas T01–T12 y flujos F01–F13 del DFD tienen cobertura.
2. Se preservan los riesgos seed: pool/RLS, dedupe, completitud, PAN, prompt injection, restore y revocación.
3. Score y severidad se calculan de forma determinista; residual siempre se identifica como proyectado, no aceptado.
4. Ningún riesgo alto/crítico queda sin tratamiento, control, prueba negativa, owner de rol y gate.
5. No existe aceptación automática ni riesgo marcado cerrado por un agente.
6. Validador, pruebas de mutación y CI pasan sin red ni datos reales.

## Verificación

```powershell
python -m tools.threat_model.validate
python -m unittest tools.threat_model.test_validate -v
```
