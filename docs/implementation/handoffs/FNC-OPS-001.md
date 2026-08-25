---
task_id: FNC-OPS-001
status: REVIEW_PENDING
base_sha: d38bc299171bbd30ee82b9b6fbdf5680e0ed13a6
reservation_sha: da18bac
tested_head_sha: bb88bc898186292884242e33c363e04c92a8c9ec
ci_run: 32796949542
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Product/Accounting, Security/Privacy, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-OPS-001 — centro operativo de ciclos y recordatorios

## Resultado

El contador que administra varias empresas dispone de `/recordatorios`: una
bandeja visual que agrega company-by-company los periodos vencidos, en gracia,
con vencimiento hoy, proximos e historicos. Cada registro conserva empresa,
fuente, periodo, fecha limite, responsable, zona horaria y un enlace al ciclo
que origino la expectativa.

Es una señal interna de trabajo. No envia correo, SMS, push o webhook; no suma
dinero, no detecta fraude y no afirma conciliacion, cierre ni entrega efectiva.
Todo el alcance sigue limitado a datos sinteticos.

## Cambios

- Proyeccion API de solo lectura sobre `source_cycle` y `source_expectation`, sin
  migracion ni segundo calendario. La evaluacion recibe un instante UTC del
  servidor y calcula la fecha local con la zona historica de cada ciclo.
- Filtros cerrados, limite 1..50 y cursor keyset por
  `(due_on, expectation_id)`. Los conteos del resumen se calculan sobre la
  ventana autorizada completa y la respuesta divulga truncamiento.
- Autorizacion `data_source.manage`, contexto de empresa server-side, RLS y
  auditoria de metadatos sin fechas financieras, correos ni valores de celdas.
- Agregador web con concurrencia acotada por empresa. Distingue vacio real,
  acceso restringido, engagement revocado, fallo parcial y respuesta truncada.
- Pantalla responsive con filtros persistidos en URL, cuatro indicadores,
  prioridad visual, responsable, fecha local y accion directa sobre la fuente.
- Cobertura API, PostgreSQL, Vitest, Playwright y Axe; la regresion de carga ya
  selecciona su fuente por identidad visible y no por posicion en un listado.

## Evidencia por aceptacion

| Criterio | Evidencia |
|---|---|
| AC-01..AC-03 | pruebas puras/API y PostgreSQL para filtros, cursor, gracia, horizonte, conteos exactos, truncamiento y zonas horarias distintas |
| AC-04..AC-05 | PostgreSQL real: permiso, RLS, cross-company, revocacion, responsable/elegibilidad y auditoria sin datos sensibles |
| AC-06..AC-07 | 134 Vitest y 16 recorridos Chromium: agregacion multiempresa, estados de acceso, URL, prioridad, detalle y limites de producto |
| AC-08 | build, tipos, lint, quality gate, 9 auditorias Axe y CI integral 32796949542 en verde sobre el head probado |

## Verificaciones ejecutadas

| Comando/carril | Resultado |
|---|---|
| API unitaria dentro de imagen | 95, OK |
| Vitest web completo | 134 en 22 archivos, OK |
| TypeScript, ESLint y Next production build | OK; `/recordatorios` dinamica |
| PostgreSQL enfocado FNC-OPS-001 | 2, OK; incluye UTC/Bogota y cross-company |
| Playwright Chromium completo | 16, OK |
| Playwright accessibility/Axe completo | 9, OK |
| quality gate sobre indice Git | OK, cero hallazgos |
| CI integral limpia | run 32796949542, todos los jobs aplicables verdes; performance manual omitido por contrato |

La repeticion local de las 292 pruebas sobre una base ya ejercida produjo dos
fallos esperables de aislamiento del laboratorio: un teardown encontro un
artefacto antiguo referenciado y la cola global tenia mas trabajos previos que
el horizonte de una prueba. No se borro el entorno de desarrollo. El carril CI
partio de volumen vacio y paso la suite PostgreSQL completa, confirmando que no
era una regresion del producto.

## Hallazgos de ejecucion

1. Evaluar todos los periodos con la zona horaria de la peticion rotulaba mal un
   ciclo historico configurado en otra zona. La API conserva un instante UTC y
   deriva `local_as_of` por fila.
2. `in_grace` y `overdue` deben ser estados separados: un periodo dentro de su
   gracia no puede presentarse como atraso.
3. La creacion de una fuente adicional revelo una prueba E2E que seleccionaba
   `option[1]`. Se corrigio para elegir `Extracto bancario (demo)` por nombre,
   evitando acoplar cargas a ordenamientos futuros.
4. Reconstruir solo `web` tambien reconstruye la imagen API por dependencias de
   Compose, pero no recrea PostgreSQL, Valkey ni el object storage.
5. Los recordatorios externos requieren contrato de canal, consentimiento,
   horarios silenciosos, reintentos, retencion y proveedor; no se insinuo su
   entrega en esta rebanada.

## Riesgos y revisiones humanas

- Product/Accounting debe confirmar los horizontes, etiquetas y la prioridad
  operativa; los conteos no representan saldos ni completitud contable.
- Security/Privacy debe revisar el permiso reutilizado, metadatos de auditoria,
  identidad mostrada del responsable y el patron company-by-company.
- Backend/Architecture debe revisar cursor, snapshot de resumen y tratamiento
  de zonas horarias historicas.
- Accessibility/QA debe revisar el orden de lectura, filtros y responsive con
  tecnologia asistiva real; Axe automatizado esta verde.
- S1-READY, DRG-00, DRG-01, ADR-002 y las decisiones humanas existentes no
  cambian de estado.

## Commits y rollback

1. `da18bac` — ficha, backlog y reserva.
2. `18bf213` — proyeccion API, ruta y pruebas de contrato/PostgreSQL.
3. `41db691` — evaluacion por zona horaria propia de cada ciclo.
4. `8a28995` — agregador y centro web, unitarias, E2E y Axe.
5. `bb88bc8` — compatibilidad de recorridos existentes y selector E2E estable.

Revertir 5 retira los ajustes de regresion; 4 retira la superficie visible; 3 y
2 retiran la proyeccion. No hay migracion, mensaje enviado ni estado financiero
que revertir.
