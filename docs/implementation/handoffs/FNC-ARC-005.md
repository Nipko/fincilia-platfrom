---
task: FNC-ARC-005
status: REVIEW_PENDING
base_sha: 209a663
implementer: Integration Steward
data_used: synthetic_only
human_acceptance: pending
---

# Handoff FNC-ARC-005

## Entrega

- Contrato narrativo endurecido y modelo ejecutable read-only.
- Manifest obliga región, subencargados y costo a estar declarados, no asumidos.
- Ocho capabilities con estado supported/unsupported/unknown pendiente de evidencia.
- Auth sin username/password/OTP/certificado privado/token raw; vault references solamente.
- Backfill/incremental, cursor company/connection/account/version, páginas y corrections.
- Identidad alineada con DOM-004; cross-source solo candidato.
- Nueve controles mínimos de completitud alineados con DOM-003.
- Retry/error taxonomy alineada con ARC-004.
- Webhook firmado/replay/digest antes de inbox.
- Ocho invariantes de fallback permanente por archivos.
- Siete estados degradados visibles; nunca asumir cero/completo.
- Controles SSRF, gateway, egress, capabilities y logs.
- Siete gates humanos de certificación y 15 escenarios requeridos.
- Validador determinista y 35 pruebas de mutación.

## Verificación

```powershell
python -m tools.connector_model.validate
python -m unittest tools.connector_model.test_validate -v
python -m tools.completeness_model.validate
python -m tools.idempotency_model.validate
python -m tools.event_model.validate
python -m tools.privacy_model.validate
python -m tools.quality_gate.cli
```

Resultado previo a integración: contrato PASS; 35/35 pruebas PASS; solo datos sintéticos,
sin red, credenciales, proveedor o IA.

## Decisiones preservadas

- Archivo es canal permanente, no parche hasta que exista API.
- Coverage/capability desconocida no equivale a soportada.
- Empty page/cursor agotado/saldo/match no prueban completitud por sí solos.
- Pending no aliasa posted; corrección crea versión.
- Adapter falla rápido; parent queue/workflow reintenta con budget.
- Feed stale/partial/provider down es visible y activa fallback.
- La plataforma no recibe credenciales bancarias ni habilita pagos.
- Ningún gate técnico acepta DPA, región, SLA o margen.

## Revisiones y pendientes

- Integrations/Product: cobertura nominal y experiencia degradada/fallback.
- Data/Accounting: controles por source/account/period.
- Security: OAuth/widget, SSRF, webhook, vault, egress y revocación.
- Privacy/Legal: rol, consentimiento, región, subencargados, DPA y retención.
- Finance: quote, FX, uso máximo, mínimos y margen.
- Crear manifests reales solo tras sandbox/acuerdos autorizados; no prometerlos antes.

## Rollback

Retirar contrato/modelo/tooling/pasos CI y restaurar schema seed. No hay conectores,
credenciales, datos o efectos externos.

Esta entrega no supera S1-READY ni autoriza datos reales o producción.
