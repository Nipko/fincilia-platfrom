---
id: FNC-WEB-001
alias: FNC-P3.7
title: Endurecimiento verificable del recorrido web P3
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 52ea3a8bad92b92acd39a33be108853d87bbe5d2
gate: S1-READY
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accessibility/QA, Security, Privacy]
---

# Resultado esperado

El recorrido web sintético existente queda confiable y verificable desde la
selección de empresa y fuente hasta carga, perfil, mapeo y navegación del dataset.
La web sigue siendo un cliente: no autoriza, calcula dinero ni publica por cuenta
propia. La aplicación móvil queda expresamente fuera de esta rebanada.

# Definition of Ready

- P3.6-R2 está integrado en `b481411`, con push y carril manual remotos verdes.
- La tarea parte del `base_sha` exacto declarado y la rama está sincronizada.
- FNC-PLT-008 y FNC-UX-001 tienen artefactos disponibles.
- `apps/web` tiene una reserva exclusiva en el grafo de trabajo.
- Sólo se usarán personas, empresas y documentos completamente sintéticos.
- No se cambia contrato API, esquema, worker, permiso ni semántica financiera.
- Las dependencias nuevas se fijan con versión exacta y lockfile.
- S1-READY permanece `not_met`; el build local no autoriza despliegue compartido.
- Una necesidad de cambiar API, persistencia, cookie, proveedor o contrato público
  se declara como dependencia; no se amplía silenciosamente esta tarea.

# Rutas permitidas

- `apps/web/**`
- `.github/workflows/ci.yml` — sólo Integration Steward.
- `docs/implementation/tasks/FNC-WEB-001.md`
- `docs/implementation/handoffs/FNC-WEB-001.md`
- Archivos centrales ya actualizados para registrar/liberar la tarea — sólo
  Integration Steward.

# Rutas prohibidas

- `apps/api/**`, `apps/mobile/**`, `db/**`, `workers/**`.
- `packages/contracts/**`, `packages/platform/**`, `infra/local/**`.
- `docs/adr/**`, gates y decisiones humanas.
- Datos reales, conectores reales y servicios externos con información financiera.

# Alcance

1. Cargar y conservar correctamente el ciclo de la fuente seleccionada.
2. Hacer visible y obligatoria la fuente del mapeo; eliminar el fallback a
   `sourceRows[0]`.
3. Conservar fuente, mapeo y página al navegar.
4. Sustituir la carga mediante Server Action por un Route Handler/BFF same-origin,
   con streaming y límite explícito.
5. Diferenciar estados 401, 403, 404, 413/415, 503 y vacío exitoso.
6. Completar accesibilidad estructural y navegación por teclado.
7. Paginar o declarar visiblemente los límites de 25, 50 y 100 elementos.
8. Añadir pruebas unitarias, E2E y accesibilidad e integrarlas en CI.

# Fuera de alcance

- Aplicación móvil, exportaciones, overrides y capacidades P4.
- Auto-match, cierre, certificación, alertas de fraude o IA.
- Persistir una fuente nueva en el artefacto si el contrato API actual no lo hace.
- Resolver en la web autorización, concurrencia de ciclos o paginación que el API
  todavía no expone; esos huecos se declaran y enrutan.

# Criterios de aceptación

- **AC-01.** Una fuente de query sólo se acepta si aparece en la respuesta
  autorizada de la empresa.
- **AC-02.** La configuración de una fuente usa un único `fetchSource`; no hay
  N+1 ni un `cycleOf` que siempre esté vacío.
- **AC-03.** Editar un ciclo conserva periodicidad, días personalizados, plazo,
  gracia, responsable, zona horaria y fecha ancla.
- **AC-04.** Un responsable ya inelegible conserva el histórico, muestra el
  estado huérfano y exige reemplazo antes de guardar.
- **AC-05.** Fuente → carga → perfil → mapeo conserva el contexto de fuente
  mientras siga siendo válido y autorizado.
- **AC-06.** Crear un mapeo exige selector visible y etiquetado; nunca elige la
  primera fuente por orden de respuesta.
- **AC-07.** Fuente, mapeo y página se componen con un helper único y sobreviven
  a paginación y selección de versión.
- **AC-08.** La carga usa un BFF same-origin; el token sale sólo de la cookie
  `httpOnly` en el servidor.
- **AC-09.** El BFF no materializa el documento completo con `formData()`,
  `arrayBuffer()` o `Buffer`, y no registra nombre, contenido, bytes ni token.
- **AC-10.** Acepta exactamente `25 * 1024 * 1024` bytes de archivo y rechaza un
  byte adicional con 413. El fixture grande se genera y nunca se versiona.
- **AC-11.** Cancelar el cliente aborta el upstream; uploads usan un deadline
  propio, no el timeout genérico de ocho segundos.
- **AC-12.** 401 lleva a ingreso; 403 muestra denegación; 404 usa `not-found`;
  413/415 explica validación; 503 muestra degradación y reintento.
- **AC-13.** Ninguna carga P3 convierte errores en listas vacías; vacío significa
  una respuesta exitosa vacía.
- **AC-14.** Existen fronteras `loading`, `error` y `not-found` aplicables.
- **AC-15.** Hay skip link, foco visible completo, captions, `scope`, errores
  asociados y `prefers-reduced-motion`.
- **AC-16.** Preview y movimientos navegan visiblemente; los demás topes fijos
  se divulgan cuando el API aún no permite paginar.
- **AC-17.** Ningún monto pasa a `Number` o `float`; se presentan cadenas
  decimales del servidor.
- **AC-18.** Pruebas unitarias, E2E y Axe pasan sólo con fixtures sintéticos.
- **AC-19.** Lint, tipos, build, auditoría de dependencias y CI remoto pasan.
- **AC-20.** El diff no toca móvil, API, DB, worker, contratos ni gates.

# Casos negativos y de abuso

- Empresa o fuente inexistente, ajena, malformada o retirada entre render y submit.
- Sesión ausente, expirada o revocada durante una carga.
- `Content-Length` ausente, falso, conflictivo o mayor al máximo de transporte.
- Archivo vacío, máximo exacto, máximo + 1 y cancelación a mitad del cuerpo.
- Upstream con cuerpo ilegible, 403, 413, 415 o 503.
- Página negativa, enorme, no numérica o repetida.
- Ciclo cuyo responsable quedó inelegible.
- Lista con exactamente el tope, posiblemente truncada.
- Nombre de fichero con controles; nunca aparece sin escape ni en logs.

# Plan de pruebas

- Pruebas puras de query params, clasificación de errores y límites de carga.
- Pruebas de componentes para selector, ciclo existente/huérfano, feedback y foco.
- Playwright E2E sobre el stack local completamente sintético.
- Axe/Playwright para `TST-A11Y-001`, sin hallazgos críticos o serios.
- Casos E2E de sesión, acceso, fuente inválida, 503 y límites 25 MiB/+1.
- Guarda que prohíbe `sourceRows[0]` y `catch(() => [])` en el recorrido P3.
- Archivos grandes generados en temporal; nunca añadidos al repositorio.

# Privacidad, observabilidad y seguridad

La web no crea una segunda autoridad ni auditoría financiera. Los errores pueden
registrar sólo código estable, ruta lógica, estado HTTP y correlation ID permitido.
Nunca token, cookie, nombre de fichero, contenido, valores de celda o cuerpo
upstream. Security revisa BFF, cookie, streaming, origen y sanitización; Privacy
confirma que no se introduce retención, telemetría ni transmisión nueva.

# Rollout y rollback

No hay migración ni feature flag. El BFF reemplaza localmente el adaptador web de
carga. Revertir los commits de FNC-WEB-001 restaura el recorrido anterior sin
tocar datos, API ni esquema. Una incompatibilidad contractual detiene la tarea y
abre trabajo separado.

# Definition of Done

- AC-01..AC-20 tienen evidencia reproducible.
- Dependencias exactas y lockfile coherente; no hay regresión high/critical.
- Lint, tipos, unit, build, E2E, accesibilidad y quality gate pasan.
- No hay secretos, PII, datos reales, fixtures grandes ni TODO sin tarea.
- Product, Accessibility/QA, Security y Privacy tienen revisión independiente
  pendiente o registrada; el implementador no se autoaprueba.
- El handoff contiene base/head, matriz AC→prueba, rutas, comandos y exit codes,
  CI, evidencia de 25 MiB/+1, memoria acotada, riesgos y rollback.
- Estado final `review_pending`; ningún agente mueve S1-READY, DRG-00 o DRG-01.

# Comandos de verificación

```bash
cd apps/web
npm ci --ignore-scripts
npm audit --audit-level=high
npm run lint
npm run typecheck
npm run test:unit
npm run build
npx --no-install playwright install chromium
npm run test:e2e
npm run test:a11y

cd ../..
python3 -B -m tools.work_graph.validate
python3 -B -m tools.test_catalog.cli validate
python3 -B -m tools.supply_chain.cli validate
python3 -B -m tools.quality_gate.cli
```

`quality_gate` se ejecuta después de indexar. Los gaps humanos preexistentes de
supply chain pueden seguir visibles; esta tarea no puede introducir uno nuevo.
