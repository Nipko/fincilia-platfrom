# Handoff — FNC-WEB-001: Endurecimiento verificable del recorrido web P3

| Campo | Valor |
|---|---|
| Tarea | `FNC-WEB-001` |
| Alias | `FNC-P3.7` |
| Estado | **`REVIEW_PENDING`** |
| Rango base | `52ea3a8` |
| `head_sha` | `1f7b22c` |
| Rama | `claude/principal-dev` |
| Owner de implementación | `Codex principal dev + Integration Steward` |
| Revisores requeridos | Product, Accessibility/QA, Security, Privacy |
| Gate de salida | `S1-READY` (sin aceptar) |
| Data ceiling | Sintético únicamente |
| Estado de gate local | No ejecutado por este agente en este tramo; requiere revalidación tras cambios de streaming |
| `integration_sha` | `pending_integration_steward` |
| `quality_gate_on_git_index` | `pending_integration_steward` |

## 1. Estado general

La rebanada está técnicamente implementada en `apps/web` y avanza desde la base
`52ea3a8...` hacia un recorrido P3 más seguro: selector de fuente obligatorio,
navegación con contexto preservado, BFF same-origin con límite explícito, estados
de error/falta/espera y pruebas nuevas para fricción de uso y abuso.

No se tocaron contratos, API, DB, workers, `packages/contracts`,
`infra/local` ni documentos raíz fuera de las rutas permitidas.

## 2. Rutas tocadas en esta entrega

- `apps/web/src/app/actions.ts`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/loading.tsx`
- `apps/web/src/app/error.tsx`
- `apps/web/src/app/not-found.tsx`
- `apps/web/src/app/empresas/[companyId]/page.tsx`
- `apps/web/src/app/empresas/[companyId]/documentos/[artifactId]/page.tsx`
- `apps/web/src/app/empresas/[companyId]/documentos/[artifactId]/mapeo/page.tsx`
- `apps/web/src/app/empresas/[companyId]/documentos/[artifactId]/mapeo/mapping-form.tsx`
- `apps/web/src/app/empresas/[companyId]/fuentes/page.tsx`
- `apps/web/src/app/empresas/[companyId]/fuentes/onboarding-forms.tsx`
- `apps/web/src/app/empresas/[companyId]/fuentes/[sourceId]/page.tsx`
- `apps/web/src/app/empresas/[companyId]/movimientos/[movementId]/page.tsx`
- `apps/web/src/app/empresas/[companyId]/upload.tsx`
- `apps/web/src/app/api/upload/route.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/cycle-date.ts`
- `apps/web/src/lib/navigation.ts`
- `apps/web/src/lib/server-config.ts`
- `apps/web/src/lib/upload-policy.ts`
- `apps/web/src/app/__tests__/route-boundaries.test.tsx`
- `apps/web/src/app/__tests__/actions.test.ts`
- `apps/web/src/lib/__tests__/navigation.test.ts`
- `apps/web/src/lib/__tests__/cycle-date.test.ts`
- `apps/web/src/lib/__tests__/upload-policy.test.ts`
- `apps/web/src/lib/__tests__/api-timeout.test.ts`
- `apps/web/tests/e2e/public-shell.spec.ts`
- `apps/web/tests/e2e/public-shell.a11y.spec.ts`
- `apps/web/tests/e2e/synthetic-upload.spec.ts`
- `apps/web/vitest.config.mts`
- `apps/web/vitest.setup.ts`
- `apps/web/playwright.config.ts`
- `apps/web/src/app/globals.css`
- `apps/web/tsconfig.json`
- `apps/web/README.md`
- `apps/web/Dockerfile`
- `apps/web/package.json`
- `apps/web/package-lock.json`
- `.github/workflows/ci.yml` (sólo lanes/lints asociados al web)

### Rutas reservadas del encargo (no modificadas)

- Contratos, API, DB, workers, mobile, ADR, gates y documentos raíz del plan.

### Rutas protegidas y estado de liberación

- No se liberan rutas fuera de `apps/web` y `.github/workflows/ci.yml`.
- `FNC-WEB-001` deja explícitamente en stand-by la parte de cierre atómico de `createMapping` para resolverse en una tarea API dedicada.

## 3. Decisiones/arquitectura aplicada

1. **BFF same-origin con control de origen estricto**: se añadió un handler en `api/upload`
   con streaming del cuerpo y límites por conexión para evitar que la web sea una
   segunda autoridad.
2. **Autenticación y contexto de empresa/usuario en servidor**: el token se mantiene
   en cookie httpOnly del adaptador de API; la web no persiste credenciales.
3. **Fuente obligatoria en mapeo**: se elimina fallback implícito y se conserva
   selección explícita de fuente en toda la navegación.
4. **Frontera de navegación estable**: helper de navegación que conserva
   `fuente/mapeo/page` entre vistas de documento, mapping y movimientos.
5. **Control antiabuso de upload**: límite de 25 MiB exacto, rechazo de `+1`, validaciones de mime/encoding,
   timeout propio para upstream y cancelación cooperativa con cliente.
6. **Accesibilidad y estados UI**: not-found, loading, error y focus-ring visible,
   navegación por teclado, captions y mensajes asociados.

## 4. Hoja de evidencia (AC objetivo)

- **AC-01** Fuente por query validada contra fuentes autorizadas y rechazada si no pertenece a la compañía.
- **AC-02** Unificación de configuración de fuente en un solo flujo de fetch; se elimina patrón de fallback implícito.
- **AC-03** Edición de ciclo preserva y exige campos obligatorios del ciclo existente.
- **AC-05** Cadena de navegación conserva contexto entre documento, mapeo y movimientos.
- **AC-06** Selector de mapeo visible y obligatorio en UI de creación; no existe auto-selección silenciosa.
- **AC-07** Paginación y versión de movimiento utilizan helper único y comparten contexto de flujo.
- **AC-08** BFF same-origin centraliza carga desde route handler interno (`/api/upload`).
- **AC-09** Upload con streaming, sin materialización de archivo completo en memoria.
- **AC-10** `maxBytes === 25 MiB` exactos y rechazo controlado de `+1`.
- **AC-11** `AbortController` propagado para cancelar upstream de carga.
- **AC-12** Branching de errores HTTP: `401/403/404/413/415/503`.
- **AC-13** Respuesta vacía expresa estado válido; no se convierte silenciosamente en lista vacía.
- **AC-14** Fronteras explícitas: `loading`, `error`, `not-found`.
- **AC-15** Accesibilidad estructural con foco visible, mensajes asociados y estados robustos.
- **AC-16** Navegación visual de preview/movimientos con límites de vista comunicados.
- **AC-17** Monto presentado como string decimal; sin cast a Number en render.
- **AC-18** Pruebas unitarias + E2E + a11y cubren recorridos positivos y negativos principales.
- **AC-19** Pendiente de revalidación integral post-lastre cambio de stream/cancel.
- **AC-20** Alcance web-only mantenido: no cambios en API/DB/mobile/contratos/gates.

## 5. Comandos ejecutados en esta rebanada

La secuencia de pruebas fue corrida en tramos anteriores y antes de los últimos
ajustes de streaming/timeout:

```bash
npm run lint
npm run typecheck
npm run test:unit
npm run build
npx --no-install playwright install chromium
npm run test:e2e
npm run test:a11y
```

Tras los cambios finales de control de streams y límites, estas pruebas deben
ejecutarse de nuevo para validar nuevamente **AC-19**.

### Cadena de verificación recomendada para el siguiente bloque

```bash
cd apps/web
npm ci --ignore-scripts
npm run lint
npm run typecheck
npm run test:unit
npm run build
npx --no-install playwright install chromium
npm run test:e2e
npm run test:a11y
```

Desde raíz, luego validar gates y calidad:

```bash
python3 -B -m tools.work_graph.validate
python3 -B -m tools.test_catalog.cli validate
python3 -B -m tools.supply_chain.cli validate
python3 -B -m tools.quality_gate.cli
```

## 6. Riesgos y pendientes técnicos (inmediatos)

1. Los cambios de control de upstream abort/cancel/no cache son funcionales pero no
   fueron reejecutados en este tramo de revalidación.
2. La acción de crear mapeo valida fuente inmediatamente con `fetchSource` para
   evitar race evidente, pero persiste TOCTOU entre esa validación y el guardado.
   Esto requiere una tarea backend (fuera de alcance) para cierre atómico.
3. Se detecta el patrón de WSL/Docker con caducidad del subsistema en algunos
   entornos; no se alteró CI por esto.

## 7. Work remaining / bloqueos por IDs

- `S1-READY` sigue `not_met` con DRG/TMGates ajenos a esta tarea.
- `DRG-00`, `DRG-01`, `DB-G03`, `ADR-002`, `TM-005` y `retry_policy_contract` no
  cambian con esta entrega y continúan bloqueando salida de fase.

## 8. Rollback

Revertir los commits asociados de `FNC-WEB-001` restaura el recorrido web previo
sin tocar API, DB ni contratos. No hay cambios irreversibles fuera de UI, handlers,
BFF y configuración de CI del web lane.

## 9. Bloque siguiente para aceleración

1. Revalidar AC-19 y adjuntar resultados con exit codes por comando en este handoff.
2. Hacer commit de los cambios de `FNC-WEB-001` y registrar la reserva de rutas.
3. Enviar al Integration Steward para que actualice `CURRENT_PHASE` y cierre `FNC-WEB-001` a `review_pending`.
4. Entregar a otro agente la siguiente rebanada P4 backend (solo si aprobamos tocar atomicidad de `createMapping`).
