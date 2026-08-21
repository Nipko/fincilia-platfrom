# Política de datos sintéticos

- Estado: Draftable
- Tarea: FNC-DAT-001

## Permitido antes de DRG-00

- Personas, empresas, NIT, cuentas y referencias inventados algorítmicamente.
- Montos/fechas generados sin derivar de registros reales.
- Logos y nombres ficticios.
- Documentos producidos desde plantillas propias.
- Archivos hostiles inocuos creados para pruebas.

## Prohibido

- Datos reales anonimizados, enmascarados o parcialmente editados.
- Capturas de pantalla, extractos, facturas o emails de clientes.
- Copiar estructura singular de un documento real no contratado.
- PII en prompts, logs, fixtures o snapshots.
- Seeds descargados de producción.

## Etiquetado

Cada fixture declara:

- synthetic: true.
- generator/version.
- scenario y locale.
- expected schema/result.
- license/provenance.
- sensitivity: synthetic.
- checksum.

Un fixture sin manifiesto se rechaza de CI.

