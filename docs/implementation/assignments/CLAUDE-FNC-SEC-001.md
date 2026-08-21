# Encargo para Claude — FNC-SEC-001

Copia desde la siguiente sección hasta “FIN DEL ENCARGO”.

---

Trabajas en el repositorio Fincilia compartido. Ejecuta exclusivamente la tarea `FNC-SEC-001` sobre la base `85c29d9`. Otro agente trabaja al mismo tiempo en el corpus sintético; no debes tocar sus rutas ni ampliar tu alcance.

## Lectura obligatoria antes de editar

Lee completos, en este orden:

1. `AGENTS.md`
2. `CURRENT_PHASE.md`
3. `docs/implementation/tasks/FNC-SEC-001.md`
4. `docs/implementation/OWNERSHIP.md`
5. `docs/product/PRD_WEDGE.md`
6. `docs/domain/TENANCY_MODEL.md`
7. `docs/security/RBAC_ABAC_SOD.md`
8. `docs/adr/ADR-003-organization-company-engagement.md`
9. `docs/implementation/DEFINITION_OF_DONE.md`

## Objetivo

Completa la matriz RBAC/ABAC/SoD y construye un kernel de autorización puro, fail-closed y ejecutable que materialice las decisiones de tenancy. Esto es un spike descartable de política, no autenticación productiva.

## Rutas que puedes modificar

- `docs/security/RBAC_ABAC_SOD.md`
- `spikes/FNC-SEC-001/**`
- `docs/implementation/handoffs/FNC-SEC-001.md`

No modifiques ninguna otra ruta. En particular, no toques `CURRENT_PHASE.md`, `AGENTS.md`, tareas, ADR, Compose, migraciones, base de datos, aplicaciones, package-lock ni archivos raíz. No uses Git: no hagas commit, checkout, pull, reset, stash ni rebase.

## Implementación requerida

Usa JavaScript ESM compatible con Node 22 y `node:test`, sin paquetes externos ni lockfile.

El kernel debe ser una función pura similar a:

```js
authorize(input) -> {
  decision: "ALLOW" | "DENY",
  reasonCodes: string[],
  obligations: string[]
}
```

Debe:

- negar campos, estados, acciones o finalidades desconocidas;
- resolver rutas directas de PYME, delegadas por engagement y service principals;
- exigir subject, assurance, membership/grant vigentes y `authorization_version` actual;
- comparar `requestedCompanyId` con `resolvedResourceCompanyId` y nunca autorizar por el ID enviado por el cliente;
- tratar organization owner/admin como administración, no acceso financiero;
- impedir que el preparador apruebe su propia preparación, regla, ajuste, reapertura o break-glass;
- modelar operación unipersonal solo mediante política explícita, step-up, razón y obligación de revisión posterior;
- usar IP, dispositivo, hora o geografía solamente como señales/obligaciones, nunca como identidad o grant;
- revalidar jobs/service principals antes de leer y antes de publicar;
- devolver reason codes estables y explicables; nunca lanzar una excepción que convierta un fallo en ALLOW.

Materializa en pruebas los 7 positivos y 16 negativos `TST-TEN-001` de `TENANCY_MODEL.md`, más casos de assurance insuficiente, SoD, finalidad incorrecta, estado desconocido y señales de dispositivo/IP. Todos los sujetos, empresas y datos deben ser inequívocamente sintéticos.

Estructura sugerida:

- `spikes/FNC-SEC-001/README.md`
- `spikes/FNC-SEC-001/src/authorize.mjs`
- `spikes/FNC-SEC-001/test/authorize.test.mjs`
- `spikes/FNC-SEC-001/test/fixtures.mjs`

El README debe explicar límites y el comando exacto `node --test`. No implementes JWT, sesiones, cifrado, UI, HTTP, SQL ni proveedor de identidad.

## Entrega y verificación

1. Ejecuta `node --test spikes/FNC-SEC-001/test/*.test.mjs` desde la raíz.
2. Ejecuta una validación de sintaxis/documentación proporcional.
3. Escribe `docs/implementation/handoffs/FNC-SEC-001.md` usando la plantilla del repositorio, con resultado exacto, archivos, riesgos y pendientes.
4. Deja el estado como `PARTIAL` o `REVIEW_PENDING`: Architecture, Accounting y Security humanos todavía deben revisar.
5. En tu respuesta final enumera rutas modificadas y resultados. No declares S1-READY ni producción lista.

Si detectas una contradicción material, no inventes una solución: documenta el bloqueo en el handoff y detente dentro de tus rutas.

FIN DEL ENCARGO
