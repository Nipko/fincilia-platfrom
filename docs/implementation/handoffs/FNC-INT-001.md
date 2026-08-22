---
task: FNC-INT-001
status: REVIEW_PENDING
base_sha: 52bf75f
integration_sha: see_git_commit_containing_this_handoff
implementer: Integration Steward
data_used: public_primary_sources_and_synthetic_only
human_acceptance: pending
---

# Handoff FNC-INT-001

## Entrega

- Matriz ejecutable de archivos, Bancolombia directo, Prometeo y Belvo.
- RFQ comparable para tres respuestas comerciales.
- 24 pruebas fail-closed sobre cobertura, credenciales, costo, gates y claims.
- Fuentes primarias verificadas al 2026-08-21.

## Resultado

File-first es la única decisión operable en E0. Bancolombia y Prometeo son candidatos de
evaluación, no proveedores seleccionados. Belvo no demuestra banking Colombia en su oferta
pública actual. Cero cotizaciones recibidas; INT-G02..G07 siguen `not_met`.

## Comandos

```powershell
python -m tools.provider_evaluation.validate
python -m unittest tools.provider_evaluation.test_validate -v
```

## Acción humana pendiente

Autorizar outreach y enviar una copia del RFQ a tres targets. Architecture, Security,
Legal y Finance revisan respuestas y solo entonces pueden adjudicar score/proveedor.

## Rollback

Retirar documentos, modelo, validador, pruebas e integración CI. No se contactó a nadie,
no hay contrato, gasto, credenciales, datos reales ni conexión que revocar.
