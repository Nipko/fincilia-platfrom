# Handoff — FNC-WEB-003: Portafolio multiempresa e historico operativo

| Campo | Valor |
|---|---|
| Tarea | `FNC-WEB-003` (`FNC-P4.3`) |
| Estado | **`REVIEW_PENDING`** |
| Base | `5565010` |
| `tested_head_sha` | `2829eb6` |
| Rama | `claude/principal-dev` |
| Implementacion | Codex principal dev + Integration Steward |
| Revisores pendientes | Product/Accounting, Security, Accessibility/QA |
| Datos | Completamente sinteticos |
| Gate | `S1-READY` sigue `not_met`; la tarea no lo mueve |
| Backend, migraciones y permisos | Ninguno modificado |

## Resultado

La entrada de empresas es ahora un portafolio operativo para una firma contable.
Por cada empresa muestra la ventana visible de documentos, cuarentena, datasets
validados pendientes de revision, preparaciones parciales y expectativas vencidas
o proximas. Son conteos de carga: no agrega importes, no calcula saldos y no
presenta una opinion de conciliacion o salud financiera.

La carga usa como maximo cuatro empresas concurrentes. Dentro de cada una solo
consulta superficies que el detalle autorizado de la empresa concede. Permiso
ausente o un 403 durante una revocacion se muestra como `Sin acceso`; un fallo
transitorio como `No disponible`. Ninguno se transforma en cero.

El puesto de mapeo permite elegir cualquiera de las hasta 50 versiones de dataset
que devolvio el API para ese artefacto. La seleccion queda en la URL y se conserva
al paginar, abrir un movimiento o volver al perfil. Un ID vacio, repetido o ajeno
no cae en la version mas reciente: queda sin seleccion y ofrece solo el historico
autorizado. Publicadas y rechazadas son de solo lectura.

## Cambios principales

- `apps/web/src/lib/portfolio.ts`
  - carga acotada y degradacion por empresa;
  - resumen puro de documentos, estados de datasets y expectativas;
  - estados tipados `available`, `restricted` y `unavailable`.
- `apps/web/src/app/empresas/page.tsx`
  - tarjetas multiempresa y lenguaje operacional explicito;
  - no llama `total` a una lista limitada: dice `en ventana`.
- vista individual de empresa
  - resumen visual de documentos, revisiones, parciales y ciclos;
  - usa permisos del servidor y no una matriz copiada en el cliente.
- `apps/web/src/lib/navigation.ts` y vistas de documento/movimiento/mapeo
  - contexto de `dataset` estable;
  - selector autorizado fail-closed para versiones historicas.
- `apps/web/src/lib/api.ts`
  - listado de datasets admite filtro por artefacto o ventana de empresa.
- CSS y pruebas
  - metricas en `dl`, selector con `aria-current` y foco del sistema existente;
  - pruebas de concurrencia, revocacion, permisos, conteos y seleccion historica.

No se tocaron API Python, base de datos, migraciones, permisos, RLS, workers,
infraestructura, CI, contratos, ADR, gates, mobile, conectores ni IA.

## Matriz de aceptacion

| Criterio | Evidencia |
|---|---|
| AC-01 | prueba de pool confirma pico <= 3 y orden estable; implementacion fija maximo 4 empresas |
| AC-02 | resumen puro y tarjetas cubren documentos, revision, parciales y ciclos |
| AC-03 | pruebas de permiso ausente y 403 exigen `restricted`, nunca valor cero |
| AC-04 | modelo de resumen no contiene amount/balance/match y la UI declara el limite |
| AC-05 | resumen individual usa las mismas funciones puras y enlaces a documentos/fuentes existentes |
| AC-06 | `dataset` entra en `FlowContext` y se conserva en perfil, paginacion y movimiento |
| AC-07 | tres pruebas de seleccion: latest implicito, ajeno/repetido fail-closed y autorizado |
| AC-08 | ramas publicadas/rechazadas no renderizan aprobacion, rechazo ni publicacion mutable |
| AC-09 | tarjetas distinguen disponible, restringido y no disponible; selector usa `aria-current` |
| AC-10 | 73 pruebas, lint, tipos, build y quality gate en verde; diff solo web/documentacion |

## Verificacion reproducida

1. `node node_modules/eslint/bin/eslint.js .`: exit 0.
2. `node node_modules/typescript/bin/tsc --noEmit`: exit 0.
3. `node node_modules/vitest/vitest.mjs run`: **73 pruebas, 13 archivos, OK**.
4. `node node_modules/next/dist/bin/next build`: exit 0; rutas dinamicas compiladas.
5. `python -B -m tools.work_graph.validate`: `ok: true` con una reserva antes de liberarla.
6. `python -B -m tools.test_catalog.cli validate`: `ok: true`, sin finding bloqueante; 13 planeados y 41 contractuales no implementados, preexistentes.
7. `python -B -m tools.quality_gate.cli`: `ok: true`, cero hallazgos sobre el indice exacto de `2829eb6`.

Se ejecutaron directamente binarios locales versionados porque el lanzador global
de npm del equipo sigue apuntando a un `npm-cli.js` inexistente. No se cambio el
equipo, el manifiesto ni el lockfile.

## Hallazgos y limites

- Los endpoints actuales limitan documentos/datasets a 50 y expectativas a 100.
  La UI dice `ventana`; un total exacto requiere paginacion/cursor server-side y
  no se invento sumando una muestra.
- El retraso (`days_late`) viene del servidor. `proximos 7 dias` es una ayuda
  visual calculada sobre fechas ISO, no cambia el estado de la expectativa.
- El primer aislamiento de prueba fallo porque una prueba antigua importaba el
  nuevo modulo server-only sin simularlo. Se corrigio el arnes; no se relajo el
  limite server-only.
- Product/Accounting debe revisar que las metricas prioricen bien el trabajo del
  contador; Security, que la degradacion no revele existencia; Accessibility/QA,
  el recorrido autenticado completo en CI.
- CI remoto no fue observado. Ningun revisor, ADR o gate fue aceptado.

## Commits y rollback

- `c2e5356` — reserva y ficha de la rebanada.
- `2829eb6` — portafolio, historico y pruebas.

Revertir `2829eb6` devuelve la lista simple de empresas y seleccion latest. No
hay datos, esquema, permiso ni migracion que revertir. La liberacion documental
se revierte por separado si la revision rechaza la entrega.
