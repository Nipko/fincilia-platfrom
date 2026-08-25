---
task_id: FNC-EXP-001
status: REVIEW_PENDING
base_sha: c1f074d0c4775e6f2b37d55f8105fdad610d2378
reservation_sha: ba2a458
tested_head_sha: 2b2033b
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Security, Backend/Architecture, Product/Accounting, Accessibility/QA]
---

# Handoff FNC-EXP-001 — exportacion canonica segura

## Resultado

Una persona con `dataset.export` puede descargar desde la version publicada un
CSV canonico estable, sin volver a interpretar el documento ni construir filas
en el navegador. El archivo se transmite API → BFF → cliente, no se persiste,
no se cachea y se rotula como salida operativa no certificada.

La funcionalidad sigue limitada a datos sinteticos. No demuestra conciliacion
de saldos, no ejecuta cierre y no modifica el dataset ni sus overlays.

## Cambios

- Permiso explicito `dataset.export`, separado de lectura y de
  `portability.export`, concedido provisionalmente a owner, preparer, reviewer y
  auditor. Security debe adjudicarlo antes de datos reales.
- Preflight API sobre estado `published`, completitud `verified`, linaje
  `complete`, manifiesto reproducible, cero rechazadas y conteos coherentes.
- CSV `canonical-v1` con columnas cerradas, orden por `record_ordinal`, UTF-8
  BOM, CRLF, fechas ISO, monto exacto a 12 decimales y defensa contra formula
  injection en descripcion y referencia.
- Cursor PostgreSQL por lotes de 1.000 y techo de 100.000 filas. La descarga no
  materializa el dataset completo ni crea un objeto en storage.
- BFF streaming con deadline conservado hasta EOF, techo de 96 MiB, token solo
  server-side, errores sanitizados y allowlist estricta de cabeceras.
- La pagina canonica ofrece `Salida limpia` solo con permiso y los cuatro sellos
  de elegibilidad; explica expresamente que no certifica saldos ni cierre.

## Evidencia por aceptacion

| Criterio | Evidencia |
|---|---|
| AC-01..AC-02 | pruebas API/PostgreSQL: estado previo 409, publicacion humana, acceso permitido, cross-company 403, RLS y auditoria sin valores |
| AC-03..AC-05 | bytes identicos, BOM, RFC4180, dinero exacto, Unicode/comillas/formulas, nombre seguro, cursor acotado y headers `no-store`/`nosniff` |
| AC-06 | 21 pruebas de policy/BFF: solo token y `Accept` upstream, streaming exacto, metadata cerrada, cancelacion y errores no reflejados |
| AC-07 | regla de elegibilidad unitaria e inspeccion visible con reviewer sobre el dataset publicado exacto |
| AC-08 | 128 Vitest, 90 API, 290 PostgreSQL, 14 Chromium, 8 Axe, tipos, lint y build verdes localmente |

## Verificaciones ejecutadas

| Comando/carril | Resultado |
|---|---|
| contratos tenancy | 28, OK |
| API unitaria en imagen | 90, OK |
| Vitest web completo | 128 en 20 archivos, OK |
| TypeScript, ESLint y Next production build | OK; ruta BFF dinamica incluida |
| foco PostgreSQL FNC-EXP-001 | 1, OK |
| suite PostgreSQL limpia completa | 290, OK; 1 omitida por contrato |
| escala PostgreSQL | 100.000 movimientos, 38,8 s total, sin duplicados |
| Playwright Chromium completo | 14, OK |
| Playwright accessibility/Axe completo | 8, OK; 0 violaciones en salida limpia |
| navegador integrado | permiso, dataset publicado, texto no certificado y enlace exacto verificados en `53000` |

El stack `fincilia-local` fue recreado desde un volumen sintetico vacio después
de detectar el checksum obsoleto de una V0016 aplicada durante la integracion
fallida anterior. V0001..V0017 migraron desde cero; los servicios quedan sanos
en `http://127.0.0.1:53000` y `http://127.0.0.1:58080`.

## Hallazgos de ejecucion

1. La primera base local conservaba el checksum anterior de V0016. El migrador
   fallo cerrado, como debe; no se reescribio historia. Se purgaron solo los
   volumenes sinteticos locales y el bootstrap limpio paso.
2. El puerto 53100 pertenece al laboratorio aislado `fincilia-rec002`; el stack
   principal se levanto en el puerto contractual 53000 sin tocarlo.
3. El primer diseño de la prueba de exportacion heredaba el caso de REC-001 y
   compartia sus sets mutables. Dejaba una fuente referenciada por un mapping y
   rompia el teardown de otra clase. Ahora usa `VerticalHarness`, colecciones
   propias y conserva un unico fixture sintetico para el E2E posterior.
4. Repetir toda la suite sobre una base ya ejercida hizo fallar correctamente
   una asercion de concurrencia que exige una entrega inicial. La corrida final
   sobre volumen vacio paso 290/290 aplicables.
5. Un fallo de stream posterior a headers no puede transformarse en JSON: el
   BFF aborta la descarga y cancela upstream. Los errores anteriores a headers
   mantienen estado publico estable y nunca reflejan detalle interno.

## Riesgos y pendientes humanos

- Security debe revisar el conjunto provisional de roles con `dataset.export`,
  la excepcion `synthetic_only`, formula injection y limites de egress.
- Backend/Architecture debe revisar cursor, transaccion de revalidacion,
  deadline y semantica de fallo a mitad del stream.
- Product/Accounting debe confirmar columnas, nombre `CSV canonico` y lenguaje
  no certificado. Esta salida no sustituye reportes, saldos ni cierres.
- Accessibility/QA debe revisar la disposicion responsive y el comportamiento
  de descarga en lectores de pantalla; Axe automatizado esta verde.
- S1-READY, DRG-00, ADR-002 y las decisiones humanas existentes no cambian.

## Commits y rollback

1. `ba2a458` — ficha, backlog y reserva.
2. `4b7f099` — permiso explicito y matriz documentada.
3. `d88d31c` — generador/API streaming y pruebas PostgreSQL.
4. `3853993` — BFF streaming, politica de cabeceras y unitarias.
5. `943a3ca` — enlace elegible, texto no certificado y layout.
6. `2b2033b` — fixture aislado, E2E de bytes y Axe.

Revertir 6 retira aceptacion automatizada; 5 retira la superficie visible; 4
retira el BFF; 3 retira el endpoint; 2 retira el permiso. No hay migracion ni
archivo persistido que revertir.
