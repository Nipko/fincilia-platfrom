# ADR-020 — región, transmisión y subencargados

- Estado: **Proposed / bloqueado por A-02**
- Fecha de propuesta: 2026-08-21
- Owners requeridos: Architecture y Legal
- Revisores: Privacy, Security, Platform y Finance
- Tarea: FNC-ARC-003

## Contexto

Fincilia procesará evidencia financiera y datos personales por company. Una región nominal
no determina por sí sola dónde operan backups, soporte, identidad, telemetría o servicios
globales, ni resuelve si cada operación es transferencia o transmisión internacional.

## Decisión propuesta

Evaluar una región primaria multi-AZ administrada en Brasil o Chile mediante la matriz A-02,
sin preferencia ni proveedor seleccionado. Cloud, egress externo, replicación cross-region y
datos reales permanecen denegados hasta completar todos los gates y firmar esta ADR.

## Alternativas

1. Región administrada en Brasil.
2. Región administrada en Chile.
3. Región en México o Estados Unidos, solo si legal, cobertura/costo y latencia la justifican.
4. Infraestructura/colocation en Colombia, a evaluar si residencia local estricta resulta
   requisito; implica mayor carga operativa y aún no tiene candidato contratado.

## Consecuencias si se acepta posteriormente

- Catálogo de servicios regionales fijado y probado.
- DPA/subencargados, soporte y ubicaciones versionados.
- Backups/DR explícitos; ninguna réplica implícita por par del proveedor.
- Exit plan y portabilidad probados antes de DRG-01.
- Cambiar región/proveedor dispara DPIA, threat review, costo y nueva ADR.

## Evidencia faltante

Los gates `A02-G01..G10` están `not_met`. No existe decisión humana, cotización comparable,
benchmark desde Bogotá, contrato aprobado ni matriz de servicios completa. Por tanto esta
ADR no autoriza despliegue.

