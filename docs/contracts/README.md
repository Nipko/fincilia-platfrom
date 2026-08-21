# Contratos compartidos

- Estado general: Draft
- Gate: S1-READY
- Owner: Architecture, UNASSIGNED

Este directorio contiene contratos independientes del lenguaje. Primero se aceptan y versionan aquí; después los paquetes de código los consumen o generan bindings.

## Reglas

- JSON Schema draft 2020-12.
- IDs y nombres internos en inglés.
- Cambios compatibles son aditivos.
- Breaking change crea nueva versión; no se reinterpreta un payload viejo.
- Eventos y jobs llevan referencias/hashes, nunca binarios, secretos o documentos completos.
- Dinero viaja como string decimal + moneda + dirección, nunca número JSON.
- Todo contrato company-scoped exige company_id.
- additionalProperties se cierra donde la extensibilidad no sea intencional.

## Carpetas

- common: valores compartidos.
- events: envelope y catálogo.
- jobs: solicitud y resultado de procesamiento.
- connectors: manifiesto y semántica de adaptadores.

