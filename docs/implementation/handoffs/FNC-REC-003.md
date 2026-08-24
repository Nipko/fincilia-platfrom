---
task_id: FNC-REC-003
status: REVIEW_PENDING
base_sha: 49339a04511fd459f1a38566654ca0d32a4453fd
reservation_sha: 4f78b58
tested_head_sha: cc6023f
data_ceiling: synthetic_only
gate_effect: none
reviewers_pending: [Product/Accounting, Security, Backend/Architecture, Accessibility/QA]
---

# Handoff FNC-REC-003 — bandeja multiempresa de revisiones

## Resultado

El contador puede abrir `/revisiones`, filtrar expedientes pendientes,
confirmados, rechazados o todos y volver al par exacto que contiene la evidencia.
La carga se hace empresa por empresa con concurrencia maxima de cuatro: no existe
una conexion firm-wide, no se omite RLS y un acceso revocado o un fallo parcial no
se presenta como cero trabajo.

La proyeccion no transporta importes ni referencias, no decide y no certifica
saldos. La estacion FNC-REC-002 conserva toda mutacion y autorizacion.

## Cambios

- La API agrega `review-queue` company-scoped con vocabulario de estado cerrado,
  offset 0..10000, limite 1..100, orden estable y señal de truncamiento.
- Cada item incorpora los dos dataset IDs derivados de los movimientos del
  ledger para reconstruir el enlace exacto, no confiados desde el navegador.
- La web valida permiso `movement.read` por empresa, limita concurrencia, ordena
  los expedientes mas antiguos primero y conserva `restricted`, `revoked` y
  `unavailable` como estados distintos.
- `/revisiones` ofrece cuatro filtros accesibles, detalle explicable y enlaces a
  la estacion. La estacion expone un ancla estable por candidato.
- El portafolio incorpora una entrada directa a la bandeja.

## Evidencia por aceptacion

| Criterio | Evidencia |
|---|---|
| AC-01..AC-03 | unitarias API + PostgreSQL real: cuatro estados, filtro invalido 422, limites, dos paginas sin duplicado, empresa alterna vacia y RLS heredada |
| AC-04 | unitarias web: sin permiso no consulta, 401 expira, 403 restringe, 404 revoca, 503 degrada y concurrencia compartida acotada |
| AC-05..AC-07 | render web, TypeScript, E2E reviewer y navegacion al candidato exacto; ninguna suma ni efecto financiero |
| AC-08 | 81 API, 106 web, 2 PostgreSQL, 6 Playwright focales, 2 Axe, lint, tipos, build, quality gate e inspeccion visual |

## Verificaciones ejecutadas

| Comando/carril | Resultado |
|---|---|
| API unitaria dentro de imagen fijada | 81, OK |
| `db.tests.test_reconciliation_decisions` contra PostgreSQL/MinIO | 2, OK sobre base con historial previo |
| Vitest web completo | 106 en 18 archivos, OK |
| TypeScript y ESLint | OK |
| Next production build | OK; `/revisiones` dinamica incluida |
| Playwright focal Chromium + accessibility | 6, OK |
| Axe bandeja y expediente | 0 violaciones |
| navegador integrado | contenido/jerarquia y layout responsive de escritorio verificados en `53100` |
| quality gate sobre cada indice Git | `ok: true`, 0 findings |

API y web del laboratorio `fincilia-rec002` se reconstruyeron conservando sus
volumenes sintéticos. La pestaña integrada queda en
`http://127.0.0.1:53100/revisiones` con Beto Revisor.

## Hallazgos de ejecucion

1. La primera prueba PostgreSQL esperaba exactamente un expediente abierto. La
   base reutilizada conservaba correctamente otro ledger append-only, por lo que
   la prueba era dependiente de vacio. Ahora localiza su candidato por ID y a la
   vez comprueba que todos los items del filtro sean abiertos.
2. `docker compose --project-directory` cambio la base de resolucion del contexto
   `../..` y apunto fuera del repositorio. Se repitio desde `infra/local`; no se
   modifico Compose ni se tocaron volumenes.
3. La bandeja limita a 50 expedientes por empresa en una carga. Si hay mas,
   muestra la empresa truncada en vez de fingir completitud; la API admite 100.
4. El laboratorio conserva expedientes de corridas previas a proposito. Esto
   ejercito orden estable, historial y tolerancia a una base no vacia.
5. El primer CI integral encontro una suposicion invalida de la prueba: el par
   conciliable es simetrico, mientras que el ledger normaliza izquierda y
   derecha por UUID de movimiento. La evidencia correcta exige ambos datasets,
   no una orientacion de carga que el dominio no promete. La asercion ahora
   compara el conjunto y conserva la validacion de pertenencia exacta.
6. El segundo CI integral ejecuto REC-002 antes de REC-003 y confirmo el unico
   expediente de una semilla vacia. REC-003 esperaba despues un pendiente que ya
   no debia existir. El recorrido abre ahora el filtro historico `Todas`: prueba
   persistencia y navegacion exacta sin fabricar estado ni depender del orden.

## Riesgos y pendientes humanos

- Product/Accounting debe revisar prioridades, lenguaje de estados y que la
  bandeja no se interprete como cierre ni conciliacion de saldos.
- Security/Backend debe revisar la estrategia company-by-company, limites y
  neutralidad ante revocacion. No existe endpoint ni rol firm-wide.
- Accessibility/QA debe revisar el orden de foco y la densidad en movil ademas
  de Axe automatizado.
- ADR-027 permanece `Proposed`; S1-READY sigue `not_met`. Ningun gate, decision
  humana o permiso se acepto o amplio.

## Commits y rollback

1. `4f78b58` — ficha, backlog y reserva.
2. `c06bbe0` — proyeccion API, filtros y PostgreSQL.
3. `cb1f2b1` — agregacion web, ruta, estados y unitarias.
4. `8bad642` — recorridos E2E y Axe.
5. `51e5d1a` — handoff y liberacion de rutas.
6. `751bec2` — semantica simetrica del par ejercida contra PostgreSQL real.
7. `cc6023f` — recorrido historico independiente del orden de la suite.

Revertir 4 retira aceptacion automatizada; 3 retira la bandeja; 2 retira la
proyeccion. No hay migracion ni datos nuevos que purgar y el ledger FNC-REC-002
queda intacto.
