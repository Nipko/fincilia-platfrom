# Solicitud de decisión A-02

- ID: `UD-A02-PROVIDER-REGION`
- Fecha: 2026-08-21
- Tareas bloqueadas: FNC-ARC-003, FNC-SEC-003, FNC-PLT-004 y DRG-01
- Owners requeridos: Architecture y Legal
- Gate afectado: A-02
- Estado: Founder direction recorded; A-02 remains Proposed

## Incertidumbre

No se conoce todavía la clasificación legal por actividad, ubicación efectiva de todos los
servicios, subencargados/soporte, DR, costo total, latencia ni salida. Seleccionar por región
de compute sería incompleto.

## Opciones

| Opción | Ventajas potenciales | Riesgos a demostrar | Reversión |
|---|---|---|---|
| Brasil administrado | Oferta regional madura entre candidatos | Legalidad, costo y posible DR/soporte externo | Media |
| Chile administrado | Región sudamericana y zonas en Azure/GCP | Cobertura servicio por servicio y contratos | Media |
| México/Estados Unidos | Cobertura/competencia potencial | Mayor distancia y análisis internacional | Media |
| Colombia dedicado/híbrido | Residencia física local potencial | Operación, disponibilidad, costo y portabilidad | Alta |

## Dirección provisional aprobada por el Founder

El 2026-08-28 el Founder autorizó priorizar **AWS `sa-east-1`** para la evaluación técnica
y económica inicial, con Cognito por invitación. El alcance de esta dirección es preparar y
validar el candidato; no equivale a aceptar A-02, no autoriza despliegue, gasto ni datos
reales y no elimina ninguno de los gates `A02-G01..G10`.

La primera etapa propuesta es un spike AWS aislado, temporal y exclusivamente sintético.
La viabilidad del Free Tier y sus límites se documentan en
`docs/architecture/aws-free-tier-evaluation.json`.

## Recomendación vigente del agente

Profundizar primero AWS São Paulo sin descartar formalmente Brasil/Chile de los demás
proveedores hasta cerrar `A02-G01..G06`; luego medir costo, latencia y salida. Mantener
local sintético y no crear recursos cloud mientras el tope autorizado siga en USD 0.

## Decisión humana

- Estado: Preferred candidate for evaluation; final decision Proposed
- Dirección provisional: `FOUNDER-01`
- Fecha de dirección provisional: 2026-08-28
- Aprobadores finales: Architecture + Legal independientes, pendientes
- ADR: ADR-020 permanece Proposed
