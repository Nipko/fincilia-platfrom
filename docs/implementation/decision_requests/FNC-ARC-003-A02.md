# Solicitud de decisión A-02

- ID: `UD-A02-PROVIDER-REGION`
- Fecha: 2026-08-21
- Tareas bloqueadas: FNC-ARC-003, FNC-SEC-003, FNC-PLT-004 y DRG-01
- Owners requeridos: Architecture y Legal
- Gate afectado: A-02
- Estado: Proposed

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

## Recomendación del agente

Cotizar y comprobar Brasil y Chile en paralelo. No puntuar ni elegir hasta cerrar
`A02-G01..G06`; luego medir costo, latencia y salida. Mantener local sintético mientras tanto.

## Decisión humana

- Estado: Proposed
- Aprobadores: UNASSIGNED
- Fecha: UNASSIGNED
- ADR: ADR-020 permanece Proposed

