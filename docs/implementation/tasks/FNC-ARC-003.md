---
task: FNC-ARC-003
title: Paquete de decisión A-02 sobre región y transmisión
status: review_pending
implementer: Integration Steward
base_sha: 87d78c5
gate: A-02
data_ceiling: synthetic_only
independent_reviewers: [Legal, Privacy, Security, Platform, Finance]
---

# Resultado esperado

Convertir A-02 en una decisión evaluable y fail-closed: inventario de planos/stores,
candidatos de ubicación sustentados por fuentes oficiales, gates legales/técnicos/económicos
y evidencia requerida antes de elegir proveedor o permitir datos reales.

## Rutas

- `docs/architecture/REGION_TRANSMISSION_DECISION.md`
- `docs/architecture/region-transmission-decision.json`
- `docs/architecture/AWS_FREE_TIER_EVALUATION.md`
- `docs/architecture/aws-free-tier-evaluation.json`
- `docs/adr/ADR-020-region-transmission-subprocessors.md`
- `tools/region_decision/**`
- `tools/aws_free_tier/**`
- `docs/implementation/decision_requests/FNC-ARC-003-A02.md`
- `docs/implementation/handoffs/FNC-ARC-003.md`
- `docs/implementation/handoffs/FNC-ARC-003-R1.md`
- Integración central por Integration Steward.

## Criterios de aceptación

1. `decision_status` y selección permanecen pendientes de aprobación humana.
2. Cada candidato tiene ubicación, fuente oficial y suitability legal desconocida.
3. Cada store/servicio declara ubicación primaria, backup, soporte y subencargados pendientes.
4. Transferencia y transmisión se evalúan por actividad/rol, no por marca del proveedor.
5. Egress, cloud y datos reales permanecen denegados hasta gates completos.
6. DR, soporte, logs, IdP, notificaciones, IA y borrado se incluyen; no solo base/object store.
7. Matriz de costo, latencia, portabilidad y disponibilidad exige evidencia reproducible.
8. El validador cruza A-02 con privacy-map y muerde selecciones o gates prematuros.
9. Una preferencia de evaluación del Founder no se confunde con selección A-02, gasto,
   despliegue o autorización de datos reales.
10. El Free Tier se separa en spike sintético, laboratorio DRG-00 y producción; ningún
    control facturable se presenta como gratuito.

## Fuera de alcance

- Aceptar región, proveedor, contrato, base legal o riesgo residual.
- Solicitar cotizaciones en nombre del usuario.
- Desplegar recursos cloud o procesar información real.
