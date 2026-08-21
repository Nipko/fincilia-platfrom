# Spike FNC-SEC-001 — Kernel de autorización

**Spike descartable de política.** No es autenticación productiva, no es un módulo de
la aplicación y no debe promoverse a `apps/` sin un ADR propio.

Materializa de forma ejecutable las decisiones de `docs/domain/TENANCY_MODEL.md` y
`docs/security/RBAC_ABAC_SOD.md` para poder **probarlas** antes de escribir código de
producto. Si el documento y el código divergen, manda el documento.

## Ejecutar

Desde la raíz del repositorio:

```bash
node --test spikes/FNC-SEC-001/test/*.test.mjs
```

Requiere **Node 22+**. No hay dependencias, ni `package.json`, ni lockfile, ni pasos de
build: solo la librería estándar y `node:test`.

Verificación de sintaxis:

```bash
node --check spikes/FNC-SEC-001/src/authorize.mjs
```

## Contrato

```js
import { authorize } from './src/authorize.mjs';

authorize(input) // -> { decision: "ALLOW" | "DENY", reasonCodes: string[], obligations: string[] }
```

`resolvePortfolio(inputs)` recalcula un portafolio empresa por empresa y devuelve los
`companyId` autorizados. Existe para que una vista consolidada nunca se sirva desde una
caché previa.

### Garantías

| Propiedad | Cómo se sostiene |
|---|---|
| **Fail-closed** | Ausencia, desconocimiento o ambigüedad producen `DENY`. La entrada se valida contra un allowlist total: un campo desconocido deniega en vez de ignorarse. |
| **Nunca lanza** | Toda la evaluación va envuelta; un fallo interno devuelve `DENY_UNSAFE_DEFAULT`, jamás `ALLOW`. Probado con getters que explotan y un `Proxy` hostil. |
| **Pura** | El instante llega en `input.now`. No se consulta el reloj del sistema, ni la red, ni disco, ni base de datos. La misma entrada da siempre el mismo resultado. |
| **No muta la entrada** | Verificado por prueba. |
| **Resultado inmutable** | `Object.freeze` sobre el resultado y sobre sus arrays; escalar a `ALLOW` desde fuera lanza `TypeError`. |

## Qué NO hace

No implementa JWT, sesiones, cifrado, hashing, UI, HTTP, SQL, RLS ni proveedor de
identidad. No consulta almacenamiento: **recibe** el recurso ya resuelto por el servidor.

El supuesto más fuerte del diseño es que quien invoque el kernel resuelve el
`company_id` desde almacenamiento autoritativo y **nunca** desde el cuerpo, el header o
el query string de la petición. El kernel compara `requestedCompanyId` contra
`resolvedResourceCompanyId` y deniega ante discrepancia, pero no puede verificar que la
resolución previa fuese correcta.

## Estructura

```text
src/catalog.mjs    vocabulario cerrado, reason codes y obligaciones
src/validate.mjs   validación estricta de entrada (allowlist total)
src/authorize.mjs  kernel: 16 etapas de decisión + resolvePortfolio
test/fixtures.mjs  fixtures sintéticos de TENANCY_MODEL.md §9.1
test/tenancy.test.mjs    TST-TEN-001: 7 positivos + 16 negativos
test/authorize.test.mjs  semántica del kernel, SoD, señales, pureza
```

## Datos

**Exclusivamente sintéticos.** Ningún identificador, nombre, NIT, correo, monto o
documento corresponde a una persona o empresa real. Los sujetos llevan el prefijo
`subject_`, las empresas `company_`, las organizaciones `firm_`/`org_` y los recursos el
sufijo `_synthetic_*`, según `TENANCY_MODEL.md` §9.1.

## Estado

61 pruebas en verde. La suite se validó además con un análisis de mutación de ocho
mutantes sobre ramas críticas; los ocho fueron detectados. Eso da evidencia de que las
pruebas ejercitan los controles y no solo el camino feliz.

**Pendiente de revisión humana de Architecture, Accounting y Security.** Los límites
conocidos de v0 están enumerados en `docs/security/RBAC_ABAC_SOD.md` §12.
