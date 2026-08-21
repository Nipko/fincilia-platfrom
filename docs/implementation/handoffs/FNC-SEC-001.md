---
task: FNC-SEC-001
status: REVIEW_PENDING
base_sha: 85c29d9
base_sha_verified: true (verified by Integration Steward)
head_sha: UNKNOWN
implementer: Claude (external agent)
data_used: synthetic_only
human_acceptance: pending
independent_reviewers_required: [Architecture, Accounting, Security]
---

# Handoff FNC-SEC-001 — Matriz y kernel de autorización

**Estado: `REVIEW_PENDING`.** No declaro esta tarea aceptada, no declaro S1-READY y no
propongo promover el spike a producto. Architecture, Accounting y Security humanos deben
revisar antes de cualquier avance de gate.

## 1. Entrega

| Ruta | Cambio |
|---|---|
| `docs/security/RBAC_ABAC_SOD.md` | Reescrito y completado: vocabulario cerrado, matriz positiva/negativa por rol y acción, atributos ABAC, SoD, operación unipersonal, señales, revocación, catálogo de reason codes, obligaciones, cobertura y ocho límites de v0. |
| `spikes/FNC-SEC-001/README.md` | Nuevo. Límites, garantías, comando de ejecución. |
| `spikes/FNC-SEC-001/src/catalog.mjs` | Nuevo. Vocabulario cerrado, reason codes, obligaciones, mínimos de assurance. |
| `spikes/FNC-SEC-001/src/validate.mjs` | Nuevo. Validación de entrada por allowlist total. |
| `spikes/FNC-SEC-001/src/authorize.mjs` | Nuevo. Kernel puro fail-closed + `resolvePortfolio`. |
| `spikes/FNC-SEC-001/test/fixtures.mjs` | Nuevo. Fixtures sintéticos de `TENANCY_MODEL.md` §9.1. |
| `spikes/FNC-SEC-001/test/tenancy.test.mjs` | Nuevo. TST-TEN-001: 7 positivos + 16 negativos. |
| `spikes/FNC-SEC-001/test/authorize.test.mjs` | Nuevo. Semántica del kernel. |
| `docs/implementation/handoffs/FNC-SEC-001.md` | Este documento. |

Ninguna otra ruta fue modificada. No se usó Git. No se crearon `package.json`, lockfiles
ni dependencias externas.

## 2. Verificación reproducible

```bash
node --test spikes/FNC-SEC-001/test/*.test.mjs
node --check spikes/FNC-SEC-001/src/authorize.mjs
```

**Resultado observado** (Node v22.20.0, 2026-08-21):

```text
# tests 61
# pass 61
# fail 0
# skipped 0
# todo 0
```

`node --check` en verde sobre los seis archivos `.mjs`. Validación de markdown: fences
balanceados y cero tablas con número de columnas inconsistente en los dos documentos
entregados. Lint de datos sintéticos sobre el spike: cero correos, cero NIT o cédulas,
cero IP, cero URLs externas, cero identificadores fuera del esquema sintético.

### 2.1 Análisis de mutación

61 pruebas en verde a la primera no demuestran nada por sí solas en un kernel de
seguridad. Verifiqué la suite inyectando ocho mutantes en ramas críticas, en una copia
fuera del repositorio. **Los ocho fueron detectados:**

| Mutante | Pruebas que fallan |
|---|---:|
| La validación de entrada devuelve ALLOW | 8 |
| Se confía en el `company_id` enviado por el cliente | 1 |
| Se elimina el chequeo de auto-aprobación (SoD) | 1 |
| Se elimina el chequeo de assurance | 3 |
| Se elimina el chequeo de `authorization_version` | 1 |
| Se elimina la denegación uniforme | 1 |
| El `catch` de seguridad devuelve ALLOW | 2 |
| Se elimina la exclusividad de operador primario | 1 |

Cada control crítico está sostenido por al menos una prueba que falla si se retira.

## 3. Cobertura

Los 23 casos de `TST-TEN-001` están materializados uno a uno con su identificador como
nombre de prueba. Además: assurance insuficiente y override de política, las cinco
reglas de SoD, operación unipersonal con y sin política aprobada, finalidad válida pero
no concedida, estado desconocido en cuatro registros distintos, campo desconocido,
bloque obligatorio ausente, señales de dispositivo e IP en sus dos direcciones,
principales no humanos, vigencia semiabierta, pureza, no mutación de la entrada,
inmutabilidad del resultado y garantía de no lanzar ante getters hostiles y `Proxy`.

## 4. Decisiones tomadas dentro del alcance

1. **Vocabulario cerrado con allowlist total.** Un campo desconocido deniega en lugar de ignorarse. Es la diferencia entre un typo que falla y un typo que autoriza.
2. **Denegación uniforme** (`DENY_NOT_FOUND_UNIFORM`) cuando el principal no tiene ninguna ruta establecida: respuesta indistinguible de recurso inexistente, probada como tal. Los códigos explicables solo se emiten a quien ya tiene relación legítima con la company.
3. **Las señales elevan la exigencia de assurance; nunca conceden.** Un dispositivo desconocido sube el mínimo a `AAL3`; señales perfectas sobre un tercero siguen denegando.
4. **La operación unipersonal exige política aprobada, motivo, step-up y revisión posterior**, las cuatro. Sin política se deniega con `OBL_SECOND_APPROVER_REQUIRED`.
5. **`resolvePortfolio` recalcula empresa por empresa** en vez de filtrar un conjunto consolidado.
6. **El kernel nunca lanza.** Cualquier fallo interno es `DENY_UNSAFE_DEFAULT`.

## 5. Riesgos y hallazgos para la revisión

Tres son observaciones sobre el **modelo**, no sobre mi implementación, y creo que
merecen decisión antes de Sprint 1.

1. **`TST-TEN-001-N09` pide atomicidad que un kernel de política no puede dar.** El caso exige que activar un segundo operador primario «se rechace de forma atómica». Mi kernel lo deniega a nivel de política, pero dos activaciones concurrentes pasarían ambas la comprobación. La garantía real necesita un índice único parcial en el esquema (un solo engagement con `is_primary_operator` activo por company). **Owner sugerido: Architecture + Database Migration Owner.** No lo abrí porque migraciones está fuera de mis rutas.

2. **`TENANCY_MODEL.md` §7 asume una entidad que §2 no define.** El flujo de invalidación habla de enlaces, exports programados, schedules, webhooks y cache keys que «se emiten con la versión observada», pero no existe un registro de *contexto emitido* en la tabla de entidades. Hoy lo modelé como la versión que porta el grant o la sesión. Si esos artefactos van a revalidarse online, necesitan ser una entidad de primera clase con su propio `authorization_version` y estado. **Owner sugerido: Architecture.**

3. **`resolvePortfolio` es tan bueno como su lista de candidatos.** Recalcula empresa por empresa, pero el conjunto de companies a evaluar lo aporta quien invoca. Si ese conjunto sale de la misma caché consolidada que N13 quiere invalidar, el recálculo no protege. Debe quedar escrito que la lista de candidatos se lee de almacenamiento autoritativo. **Owner sugerido: Backend + Security.**

4. **La segregación se evalúa por `subject_id`, no por persona natural.** Dos `subject_id` distintos de la misma persona eluden SoD. Resolverlo exige una decisión de identidad fuera de esta tarea. Documentado en `RBAC_ABAC_SOD.md` §6.

5. **`grant.issue` no está acotado por rango.** Falta la regla que impida a un principal emitir un grant más amplio que el suyo. El kernel lo trata como una acción más.

6. **El supuesto más fuerte no es verificable desde aquí.** El kernel compara `requestedCompanyId` contra `resolvedResourceCompanyId` y deniega ante discrepancia, pero no puede comprobar que la resolución previa se hiciera contra almacenamiento autoritativo. Si esa capa se equivoca, el kernel autoriza sobre una premisa falsa. Es el punto que más merece atención en el threat model.

Los ocho límites de v0 están enumerados en `docs/security/RBAC_ABAC_SOD.md` §12.

## 6. Bloqueos y desviaciones declaradas

1. **No pude verificar la base `85c29d9`.** El encargo prohíbe usar Git. Registro el SHA declarado en la ficha como no verificado y no puedo aportar head SHA.
2. **No ejecuté `python -m tools.quality_gate.cli`.** Ese gate apareció en el repositorio durante mi trabajo (FNC-PLT-003, otro agente) y escanea el **índice de Git**; mis archivos son nuevos y no están indexados, así que no los cubriría, y ejecutarlo implicaría Git. **El Integration Steward debe ejecutarlo después de indexar estas rutas.**
3. **Tensión con `DEFINITION_OF_DONE.md`.** El DoD exige base/head SHA y CI verde sobre el commit entregado. Ninguna de las dos cosas es alcanzable bajo las restricciones de este encargo. Por eso el estado es `REVIEW_PENDING` y no `Done`: la brecha la cierra quien integre, no yo.
4. **`docs/security/THREAT_MODEL.md` no fue tocado** pese a que los hallazgos §5.1, §5.2 y §5.6 le corresponden. Está fuera de mis rutas.

## 7. Revisión solicitada

- **Architecture:** los hallazgos 1, 2 y 3 de §5; el orden de las 16 etapas de decisión; si la denegación uniforme deja suficiente trazabilidad para soporte.
- **Accounting:** la matriz de §4 de `RBAC_ABAC_SOD.md` frente al proceso contable real, sobre todo qué roles pueden recibir `close.approve` y `close.reopen.approve`, y si la exclusividad del operador primario refleja la práctica de una firma con cartera.
- **Security:** el catálogo de reason codes como contrato estable; la política de señales; el hallazgo 6 de §5; si la operación unipersonal, tal como está, es aceptable como control compensatorio.

No marcar esta tarea `Done`, no promover `spikes/FNC-SEC-001/` a `apps/` y no consolidar
S1-READY a partir de este handoff.

## 8. Addendum de revisión del Integration Steward

Revisión independiente ejecutada sobre `45b16a9` antes de integrar:

- `node --test`: 61/61 PASS.
- `node --check`: PASS sobre todos los `.mjs`.
- Quality gate sobre las rutas entregadas: PASS después de sustituir un falso positivo lingüístico (`Todo valor`) por `Cada valor`; no cambió semántica.
- El scope coincide con el encargo y no contiene dependencias, lockfiles ni datos reales.

La revisión confirma tres brechas adicionales que bloquean promoción productiva:

1. La tabla §4 declara que `✘` debe denegar aun ante un grant mal emitido, pero el kernel no aplica una allowlist rol→acción cuando el grant existe; además `companyMembership` no porta roles. Debe resolverse como contrato de policy, no confiando solo en issuance.
2. Un service principal propiedad directa de una company no tiene ruta positiva funcional: la rama `direct` exige un `companyMembership` humano. Un service principal propiedad de organization tampoco exige hoy `organizationStatus=active`.
3. Acción, resource kind y purpose se validan individualmente, pero no como tupla compatible. Un grant mal configurado podría combinar términos válidos semánticamente incompatibles.

Estas brechas no invalidan el valor del spike fail-closed ni sus pruebas de tenancy, pero exigen una tarea de hardening antes de materializar autorización en el monolito. FNC-SEC-001 permanece `REVIEW_PENDING`.
