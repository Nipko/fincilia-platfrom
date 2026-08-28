# Matriz L-01 de retención y borrado

Este documento describe el contrato ejecutable de FNC-PRV-002. No fija plazos
ni constituye concepto jurídico. El borrador vigente es válido porque conserva
las 19 decisiones pendientes; no porque L-01 esté satisfecho.

El archivo `retention-deletion-matrix.json` se liga al contenido canónico de
`privacy-map.json`. Si cambia una política, evento, store, derivado, método de
purga o regla de restore, la matriz queda obsoleta y falla cerrada.

## Inventario que debe adjudicar Legal

| Política | Clase | Inicio del reloj | Stores |
|---|---|---|---|
| L-01-IDENTITY | Identidad y sesión | Último evento de identidad o sesión | PostgreSQL, Valkey |
| L-01-QUARANTINE | Artefacto no confiable | Recepción de la versión | Cuarentena |
| L-01-RAW | Evidencia original aceptada | Aceptación de la versión | Raw |
| L-01-DERIVED | Dataset/manifiesto derivado | Creación de la versión | Derived |
| L-01-FINANCIAL | Registro financiero canónico | Último asiento o documento relacionado | PostgreSQL |
| L-01-CLOSE | Evidencia de cierre | Sellado del snapshot | Derived |
| L-01-EXPORT | Export efímero | Materialización | Derived |
| L-01-SOURCE-EVENT | Evento de proveedor | Recepción | PostgreSQL |
| L-01-AUDIT | Auditoría de seguridad/decisión | Escritura del evento | Archivo de seguridad |
| L-01-DELETE-LEDGER | Tombstone/delete ledger | Escritura del tombstone | Archivo de seguridad |
| L-01-PRIVACY-REQUEST | Solicitud de privacidad | Cierre de la solicitud | PostgreSQL, archivo de seguridad |
| L-01-AUTHORIZATION | Autorización/revocación | Cambio de estado | PostgreSQL, archivo de seguridad |
| L-01-AUDITABLE-DECISION | Decisión operativa | Registro de la decisión | PostgreSQL |
| L-02-AI-CALL | Registro minimizado de IA | Registro de la llamada | PostgreSQL |
| L-01-NOTIFICATION | Despacho de notificación | Despacho | PostgreSQL |
| L-01-BILLING | Facturación y uso | Cierre de factura o periodo | PostgreSQL, proyección |
| L-01-BACKUP | Copia de recuperación | Creación del set | Backups |
| L-01-TELEMETRY | Observabilidad | Emisión del evento | Logs, proyección |
| L-01-DEVICE | Estado local | Escritura local | Navegador, dispositivo |

Los hechos técnicos de cada fila no se duplican en la matriz: se leen de la
fuente ligada por digest. La matriz sólo contiene la adjudicación humana:
`retention_days`, fundamento, contrato, excepciones, vigencia y evidencia.

## Semántica del plazo

La unidad operativa es `calendar_days`, entero entre 1 y 36.500. Legal debe
traducir la obligación o acuerdo a un valor ejecutable y conservar el fundamento
externo. Esa traducción no cambia el evento inicial definido en privacy-map.

Dos restricciones son obligatorias:

- `L-01-FINANCIAL` no empieza en la carga; empieza en el último asiento o
  documento relacionado, para no borrar soporte de un periodo reabierto.
- `L-01-DELETE-LEDGER` debe durar más que `L-01-BACKUP`; de otro modo un restore
  podría resucitar una supresión después de perder el tombstone.

## Borrado verificable

Una solicitud debe resolver alcance en la fuente autoritativa por empresa,
validar holds, escribir tombstone, purgar stores activos y derivados, esperar la
ventana de backup y reconciliar el inventario. Sólo entonces puede quedar
`completed`. Los exports efímeros forman parte del inventario.

Un restore no reabre servicio hasta reaplicar tombstones y reconciliar. El
delete ledger vive fuera del restore ordinario. Ninguna caché o proyección
decide el alcance de la supresión.

## Estados y segregación

`review_pending` exige todas las decisiones humanas vacías, cuatro signoffs
pendientes y L-01 cerrado. `adjudicated` sólo sería válido con:

1. 19 filas completas, sin adjudicación parcial.
2. Abogado nominal distinto de `FOUNDER-01`, competencia y concepto referenciados.
3. Vistos buenos distintos de Legal, Privacy, Security y Accounting.
4. Plazo del delete ledger mayor al backup.
5. Sólo L-01 en `met`; DRG-00 y DRG-01 continúan `not_met`.

Los nombres civiles, conceptos, firmas y contratos se custodian fuera de Git.
Aquí sólo se guardan alias estables y referencias no secretas a evidencia.

## Verificación

```text
python -m tools.retention_matrix validate
python -m tools.retention_matrix report
python -m unittest tools.retention_matrix.test_model
```

`ok: true` en el borrador significa que no falta ninguna pregunta. Consulte
siempre `human_adjudication`, `l01_met` y `real_data_authorized` por separado.
