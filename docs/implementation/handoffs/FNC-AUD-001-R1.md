---
task_id: FNC-AUD-001-R1
status: REVIEW_PENDING
base_sha: 21bb945
corrects: FNC-AUD-001
implementation_sha: pending
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security/Privacy, Backend/Architecture, Web/Accessibility]
---

# Correccion de evidencia FNC-AUD-001-R1

## Motivo

El handoff original dejo la inspeccion visual completa como no demostrada porque
el runtime Docker dentro de WSL terminaba al finalizar la sesion que lo sostenia.
FNC-PLT-009 corrigio ese lifecycle. Esta correccion agrega evidencia posterior y
no modifica ni sustituye el handoff entregado de FNC-AUD-001.

## Evidencia visual posterior

La prueba se ejecuto el 2026-08-25 contra el stack sintetico persistente en
`http://127.0.0.1:53000`:

- Inicio de sesion con una identidad sintetica y llegada al portafolio: OK.
- Acceso desde el portafolio al centro `Accesos y auditoria`: OK.
- Vista multiempresa: 5 empresas visibles, 113 eventos visibles, 89 permitidos,
  24 denegados y 0 errores. Cuatro empresas indicaron que tenian mas eventos.
- Filtro combinado por Transportes Andinos SAS, resultado denegado y accion
  exacta `company.access`: 37 eventos, todos de la empresa y accion seleccionadas,
  0 permitidos, 37 denegados y 0 errores.
- La interfaz mostro actor, empresa, accion, tipo, resultado e instante, sin
  exponer `detail`, `resource_ref`, valores financieros ni secretos.
- Al retirar accion y resultado, manteniendo la empresa, aparecio `Eventos
  anteriores`. La navegacion cargo una segunda pagina con cursor opaco y filas
  validas sin abandonar el contexto de empresa.

La prueba complementa las 28 pruebas PostgreSQL/HTTP que ya verificaban dos
paginas sin solapamiento. No mueve S1-READY ni reemplaza la revision independiente.

## Limites y revision pendiente

Solo se usaron fixtures sinteticos. Security/Privacy aun debe revisar RLS,
identidad laboral y minimizacion; Backend/Architecture, keyset y limites; y
Web/Accessibility, estados parciales y recorrido. `FOUNDER-01` y el implementador
no cuentan como revisores independientes.

## Rutas liberadas

`docs/implementation/handoffs/FNC-AUD-001-R1.md` y la referencia de evidencia en
`docs/implementation/TRACEABILITY.md`.
