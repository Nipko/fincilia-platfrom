---
id: FNC-CLN-004
title: Rango, preview canonico y plantillas de limpieza reutilizables
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: faf93927c61fd50ff23a7f5b62f581e491a51fde
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Accounting, Data, Security, Database, Backend/Architecture, Product, Accessibility/QA]
---

# Resultado esperado

Convertir el mapeo en un limpiador visual verificable antes de guardar. El
operador puede acotar el final de los datos, excluir columnas, ver una muestra
canonica producida por el mismo dominio que prepara el dataset y reutilizar una
plantilla estable sobre otro documento de la misma fuente creando una version
nueva e inmutable.

# Autoridad y decisiones aplicables

- ADR-001 mantiene parsing y extraccion en el worker; este bloque consume
  `raw_record` ya promovido y nunca interpreta el archivo original en la web.
- ADR-005 exige conservar las coordenadas fisicas aunque una vista omita filas o
  columnas.
- ADR-024 ata el plan reproducible a `(mapping_version_id, engine_release_id)`;
  reutilizar una plantilla crea otra version, nunca reescribe la anterior.
- `column_mapping` es la plantilla estable existente y
  `column_mapping_version` su historial. No se crea un segundo modelo paralelo.

# Rutas reservadas

- `packages/contracts/python/fincilia_contracts/mapping.py` y pruebas focales.
- `apps/api/src/fincilia_api/datasets.py`, `routes.py` y pruebas focales.
- `apps/web/src/lib/api.ts`, `lib/navigation.ts`, `app/actions.ts`, estudio de
  mapeo, estilos y pruebas.
- BFF de carga y su prueba focal, ampliado al demostrar en E2E que cancelar un
  stream todavia bloqueado interrumpia cargas pequenas validas.
- Formulario de carga, ampliado para impedir submit nativo antes de hidratacion;
  el hallazgo aparecio al encadenar dos documentos para reutilizar la plantilla.
- `db/tests/test_p3_vertical.py`.
- E2E/Axe de mapeo y esta ficha/handoff.
- Registros centrales, CI o contratos compartidos solo por Integration Steward.

# Fuera de alcance

- Mutar o borrar `source_artifact`, `raw_record`, versiones o datasets.
- Fusionar hojas/documentos, expresiones libres, formulas, scripts o IA.
- Transformaciones que calculen importes con reglas distintas al dominio
  determinista vigente.
- Datos reales, movil, auto-match, publicacion automatica o cierre.
- Promover gates, aceptar ADR o sustituir revision humana independiente.

# Criterios de aceptacion

- **AC-01.** `last_data_row` es opcional, inclusivo y validado: nunca precede a
  `first_data_row`; conteos, lotes y manifest respetan exactamente el rango.
- **AC-02.** El preview canónico es read-only, requiere `dataset.map`, usa el
  mismo parser decimal/fecha/direccion que la preparacion y no persiste dataset,
  movimientos ni valores en auditoria.
- **AC-03.** Una configuracion incompleta devuelve blockers explicitos; una fila
  invalida aparece como rechazo de muestra y nunca como movimiento plausible.
- **AC-04.** La web muestra antes de guardar: filas incluidas, columnas omitidas,
  muestra canonica, rechazos y si la muestra/rango estan truncados.
- **AC-05.** Las plantillas se listan por empresa y fuente. Aplicar una crea una
  version nueva bajo la plantilla existente, ligada al artefacto destino.
- **AC-06.** Reutilizacion exacta es idempotente; dos solicitudes concurrentes no
  duplican una version. Drift de esquema se muestra y falla cerrado al guardar.
- **AC-07.** Referencias cross-company, fuente distinta o plantilla malformada
  devuelven una negativa neutral y no escriben nada.
- **AC-08.** Cada preview y aplicacion registra solo metadatos acotados; ninguna
  celda, descripcion, referencia o importe aparece en auditoria o logs.
- **AC-09.** Pruebas de dominio, API, PostgreSQL real, web, E2E y Axe pasan; CI
  queda verde y S1-READY no cambia.

# Rollout y rollback

Rollout local y solo con corpus sintetico. `last_data_row` amplía de forma
compatible el JSON versionado; su ausencia conserva el comportamiento actual.
El rollback funcional oculta preview/reutilizacion y deja intactas las versiones
ya creadas. No se edita ninguna migracion aplicada.
