# RBAC, ABAC y segregación v0

- Estado: Review pending — requiere revisión humana de Architecture, Accounting y Security
- Tarea: FNC-SEC-001
- ADR: ADR-003 (Accepted)
- Gate: S1-READY
- Datos permitidos: exclusivamente sintéticos
- Kernel ejecutable de referencia: `spikes/FNC-SEC-001/` (spike descartable, no productivo)

Este documento define **qué se decide**. El kernel de `spikes/FNC-SEC-001/` es la
materialización ejecutable y probada de estas reglas; ante divergencia, este documento
manda y el spike debe corregirse, nunca al revés.

Aprobar este documento no supera S1-READY ni autoriza datos reales.

---

## 1. Principio

Una acción se autoriza cuando **todas** las condiciones de la §6.1 de
`docs/domain/TENANCY_MODEL.md` se cumplen simultáneamente sobre el recurso
**resuelto por el servidor**. Cualquier dato faltante, estado desconocido, versión
obsoleta o conflicto de segregación produce `DENY`.

Tres reglas gobiernan todo lo demás:

1. **Rol ≠ permiso.** El rol es un atributo de política. El permiso efectivo siempre exige un `grant` vigente.
2. **Administración ≠ finanzas.** Owner, Firm Admin y Billing Admin gobiernan la organización; no leen ni mutan datos financieros de una company sin grant propio.
3. **Señal ≠ identidad.** IP, dispositivo, hora y geografía elevan la exigencia o generan obligaciones; nunca identifican, nunca conceden y nunca sustituyen un grant.

---

## 2. Vocabulario cerrado

El kernel deniega cualquier término fuera de estos conjuntos. Un vocabulario abierto
convierte un error de escritura en un `ALLOW` silencioso.

### 2.1 Acciones

| Grupo | Acciones |
|---|---|
| Lectura financiera | `financial.read`, `movement.list`, `audit.read` |
| Escritura financiera | `financial.write`, `adjustment.prepare`, `adjustment.approve` |
| Salida operativa acotada | `dataset.export` |
| Ciclo de cierre | `close.prepare`, `close.approve`, `close.reopen.request`, `close.reopen.approve` |
| Reglas | `rule.author`, `rule.release.approve` |
| Portabilidad | `portability.read`, `portability.export` |
| Relación | `engagement.transfer.initiate`, `engagement.primary_operator.activate`, `grant.issue` |
| No humano | `job.execute`, `job.publish` |
| Excepcional | `break_glass.execute`, `break_glass.review` |
| Administrativo puro | `org.billing.manage`, `org.member.manage` |

### 2.2 Finalidades

`operate` · `review` · `audit.read` · `portability` · `administration` · `incident_response`

### 2.3 Recursos

`movement` · `dataset` · `close_period` · `adjustment` · `rule` · `evidence_document` ·
`portability_package` · `engagement` · `grant` · `audit_log` · `org_settings`

### 2.4 Niveles de assurance

`AAL1` < `AAL2` < `AAL3`. `AAL3` es el step-up.

El mínimo efectivo es el **máximo** entre el mínimo de la acción, el `minimum_assurance`
del grant, el override de política del tenant y cualquier elevación por señal de riesgo.

| Acción | Mínimo por defecto |
|---|---|
| `job.execute`, `job.publish` | `AAL1` |
| Lectura financiera, `dataset.export`, `financial.write`, `adjustment.*`, `close.prepare`, `close.reopen.request`, `rule.author`, `portability.read`, `org.billing.manage` | `AAL2` |
| `close.approve`, `close.reopen.approve`, `rule.release.approve`, `portability.export`, `grant.issue`, `engagement.*`, `break_glass.*`, `org.member.manage` | `AAL3` |

---

## 3. Roles base

| Rol | Alcance | Capacidades sujetas a grant | No implica |
|---|---|---|---|
| Organization Owner | Organización | Billing, miembros, configuración | **Ningún** acceso financiero |
| Firm Admin | Firma | Equipo, engagements, asignaciones | Cerrar empresas del portafolio |
| Billing Admin | Organización | Plan, consumo y pagos | Ver movimientos ni evidencia |
| Company Admin | Empresa | Equipo y configuración de la empresa | Saltar SoD |
| Preparer | Empresa/ciclo | Importar, mapear, proponer, comentar | Aprobar su propia preparación |
| Reviewer | Empresa/ciclo | Revisar matches y excepciones | Cierre final automático |
| Close Approver | Empresa/ciclo | Aprobar cierre y reapertura | Preparar y aprobar el mismo control |
| Auditor | Empresa/periodo | Lectura de evidencia y auditoría | Cualquier mutación |
| Viewer | Empresa | Lectura autorizada | Exportación privilegiada |
| Client Collaborator | Solicitud | Subir, responder, comentar | Ver la cartera de la firma |

Los roles administrativos son `organization_owner`, `firm_admin`, `billing_admin` y
`company_admin`. El kernel emite `DENY_ADMIN_ROLE_NOT_FINANCIAL` cuando uno de ellos
intenta una acción financiera sin grant propio.

---

## 4. Matriz positiva y negativa por rol y acción

`✔` el rol puede recibir un grant para esa acción · `SoD` puede, salvo conflicto de
segregación (§6) · `✘` la política deniega aunque exista un grant mal emitido.

| Rol | `financial.read` / `movement.list` | `dataset.export` | `financial.write` | `close.prepare` | `close.approve` | `close.reopen.request` | `close.reopen.approve` | `rule.author` | `rule.release.approve` | `portability.export` | `grant.issue` | `audit.read` | `org.*.manage` |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Organization Owner | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ |
| Firm Admin | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ | ✔ |
| Billing Admin | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✔ |
| Company Admin | ✔ | ✔ | ✘ | ✘ | ✘ | ✔ | ✘ | ✘ | ✘ | ✔ | ✔ | ✔ | ✔ |
| Preparer | ✔ | ✔ | ✔ | ✔ | ✘ | ✔ | ✘ | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ |
| Reviewer | ✔ | ✔ | ✘ | ✘ | SoD | ✔ | SoD | ✘ | SoD | ✘ | ✘ | ✔ | ✘ |
| Close Approver | ✔ | ✘ | ✘ | ✘ | SoD | ✔ | SoD | ✘ | SoD | ✘ | ✘ | ✔ | ✘ |
| Auditor | ✔ | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✔ | ✘ |
| Viewer | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |
| Client Collaborator | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |

Restricción adicional e independiente del rol: `financial.write`, `close.prepare`,
`close.approve` y `close.reopen.approve` **solo** se conceden por vía delegada al
engagement designado `primary_accounting_operator`
(`TENANCY_MODEL.md` §5.3.2 → `DENY_NOT_PRIMARY_OPERATOR`). Los miembros directos de la
company no están sujetos a esa exclusividad, pero sí a SoD.

`dataset.export` es una salida operativa de **un** dataset canónico ya publicado;
no crea un paquete de portabilidad, no incluye evidencia original ni sustituye
`portability.export`. Sigue siendo egress financiero: exige grant propio, AAL2,
auditoría sin valores y no se deriva de `financial.read`. FNC-EXP-001 sólo la
materializa sobre datos sintéticos; Security debe revisar esta ampliación antes
de habilitar datos reales.

---

## 5. Atributos de decisión (ABAC)

| Atributo | Origen autoritativo | Efecto |
|---|---|---|
| `subject_id` | Registro de subject | Identidad de autorización. **Nunca** el email. |
| `assurance` | Sesión autenticada | Compara contra el mínimo efectivo (§2.4). |
| `organization_membership` / `company_membership` | Registro de membresía | Precondición de ruta. |
| `engagement` | Registro de engagement | Precondición de ruta delegada. |
| `grant` | Registro de grant | Única base de allow efectivo. |
| `company_id` | **Recurso resuelto server-side** | Frontera de toda decisión. |
| Recurso, acción, finalidad | Solicitud validada contra vocabulario cerrado | Deben estar en el grant. |
| Estado de company y de recurso | Registro | Restringe mutaciones. |
| `authorization_version` | Company, no caché | Invalida contextos previos. |
| Responsabilidad operativa y `asset_ownership` | Registros propios | Atributo de política; **nunca** autoriza. |
| Política de SoD | Configuración del tenant | Un deny prevalece sobre cualquier allow. |

IP, dispositivo, hora y geografía **no** aparecen en esta tabla como base de decisión:
se tratan en §7.

---

## 6. Segregación de funciones

| Acción A | Acción B incompatible sobre el mismo control | Reason code |
|---|---|---|
| Preparar ajuste o cierre material | Aprobar ese ajuste o cierre | `DENY_SOD_SELF_APPROVAL` |
| Crear o cambiar una regla con impacto | Aprobar el release de esa regla | `DENY_SOD_RULE_AUTHOR_APPROVAL` |
| Solicitar una reapertura | Aprobar esa reapertura | `DENY_SOD_REOPEN_SELF_APPROVAL` |
| Ejecutar un break-glass | Revisar o aprobar ese mismo acceso | `DENY_SOD_BREAK_GLASS_SELF_REVIEW` |
| Administrar un grant privilegiado | Ser su único revisor | Revisión independiente obligatoria |

La segregación se evalúa por **`subject_id`**, no por credencial: dos identidades del
mismo subject no eluden la regla. Un deny de segregación prevalece sobre la unión de
roles y sobre pertenecer a la firma operadora primaria.

> **Límite conocido de v0.** El kernel separa por `subject_id`. No detecta que dos
> `subject_id` distintos correspondan a la misma persona natural. La resolución
> persona↔subject requiere una decisión de identidad que excede FNC-SEC-001 y queda
> registrada como pendiente en el handoff.

### 6.1 Operación unipersonal

Cuando no existe un aprobador independiente disponible, el cierre **no se autoriza por
omisión**. Requiere las cuatro condiciones a la vez:

1. política explícita aprobada, con identificador;
2. motivo registrado;
3. step-up a `AAL3`;
4. obligación de revisión posterior.

Sin política se emite `DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY` junto con la obligación
`OBL_SECOND_APPROVER_REQUIRED`. Con política se autoriza emitiendo
`OBL_REASON_REQUIRED`, `OBL_POST_REVIEW_REQUIRED` y `OBL_STEP_UP_REQUIRED`. No existe
bypass silencioso.

---

## 7. Señales de riesgo

| Señal | Efecto permitido | Efecto prohibido |
|---|---|---|
| Dispositivo desconocido | Eleva el mínimo a `AAL3`; `OBL_AUDIT_HIGH_RISK_SIGNAL` | Identificar al sujeto |
| IP marcada | Eleva el mínimo a `AAL3`; obligación de auditoría | Sustituir autenticación |
| Salto geográfico anómalo | Eleva el mínimo a `AAL3`; obligación de auditoría | Conceder o denegar por sí solo |
| Fuera de horario | `OBL_AUDIT_HIGH_RISK_SIGNAL` | Denegar por sí solo |

Una señal favorable **nunca** compensa la ausencia de grant, ruta, versión o assurance.
Una IP conocida no es una credencial.

---

## 8. Revocación e invalidación

Toda mutación que reduce acceso incrementa `company.authorization_version` en la misma
transacción y arrastra: grants, sesiones, scopes de jobs, enlaces de solo lectura,
exports programados, schedules, webhooks, service principals y namespaces de caché
derivados (`TENANCY_MODEL.md` §7).

El kernel comprueba la versión **dos veces** para trabajo no humano: antes de leer y
antes de publicar (`OBL_REVALIDATE_BEFORE_READ`, `OBL_REVALIDATE_BEFORE_PUBLISH`). Un
job iniciado con la versión anterior aborta antes de confirmar efectos.

Una vista consolidada de portafolio se **recalcula empresa por empresa**; nunca se sirve
desde una caché consolidada previa.

---

## 9. Catálogo de reason codes

Contrato estable y explicable. Un `DENY` nunca devuelve texto libre.

### 9.1 Allow

`ALLOW_DIRECT_PATH` · `ALLOW_DELEGATED_PATH` · `ALLOW_SERVICE_PRINCIPAL` · `ALLOW_PORTABILITY_SCOPE`

### 9.2 Deny

| Familia | Códigos |
|---|---|
| Entrada | `DENY_MALFORMED_INPUT`, `DENY_UNKNOWN_FIELD`, `DENY_UNKNOWN_ACTION`, `DENY_UNKNOWN_PURPOSE`, `DENY_UNKNOWN_RESOURCE_KIND`, `DENY_UNKNOWN_STATE`, `DENY_UNKNOWN_PHASE`, `DENY_UNSAFE_DEFAULT` |
| Principal | `DENY_SUBJECT_NOT_ACTIVE`, `DENY_IDENTITY_NOT_ACTIVE`, `DENY_SESSION_NOT_ACTIVE`, `DENY_SUBJECT_MISMATCH_GRANT` |
| Assurance | `DENY_ASSURANCE_INSUFFICIENT` |
| Empresa | `DENY_COMPANY_SCOPE_MISMATCH`, `DENY_COMPANY_STATE_FORBIDS_ACTION`, `DENY_RESOURCE_NOT_RESOLVED`, `DENY_NOT_FOUND_UNIFORM` |
| Ruta | `DENY_PATH_MISSING`, `DENY_PATH_MEMBERSHIP_NOT_ACTIVE`, `DENY_PATH_ENGAGEMENT_NOT_ACTIVE`, `DENY_PATH_ENGAGEMENT_ORG_MISMATCH`, `DENY_PATH_ENGAGEMENT_COMPANY_MISMATCH`, `DENY_PATH_NOT_REFERENCED_BY_GRANT`, `DENY_ENGAGEMENT_FROZEN_ACTION_NOT_ALLOWLISTED` |
| Grant | `DENY_NO_GRANT`, `DENY_GRANT_NOT_ACTIVE`, `DENY_GRANT_OUT_OF_VALIDITY`, `DENY_GRANT_COMPANY_MISMATCH`, `DENY_GRANT_ACTION_MISMATCH`, `DENY_GRANT_PURPOSE_MISMATCH`, `DENY_GRANT_RESOURCE_MISMATCH`, `DENY_AUTHORIZATION_VERSION_STALE` |
| Confusión de dimensiones | `DENY_ADMIN_ROLE_NOT_FINANCIAL`, `DENY_ASSET_OWNERSHIP_NOT_AUTHORIZATION`, `DENY_RESPONSIBILITY_NOT_AUTHORIZATION` |
| Operador primario | `DENY_PRIMARY_OPERATOR_CONFLICT`, `DENY_NOT_PRIMARY_OPERATOR` |
| Segregación | `DENY_SOD_SELF_APPROVAL`, `DENY_SOD_RULE_AUTHOR_APPROVAL`, `DENY_SOD_REOPEN_SELF_APPROVAL`, `DENY_SOD_BREAK_GLASS_SELF_REVIEW`, `DENY_SOD_SINGLE_OPERATOR_WITHOUT_POLICY` |
| No humano | `DENY_SP_NOT_ACTIVE`, `DENY_SP_CREDENTIAL_NOT_ACTIVE`, `DENY_SP_ROUTE_MISMATCH`, `DENY_SP_TARGET_COMPANY_MISMATCH` |
| Recurso | `DENY_RESOURCE_STATE_FORBIDS_ACTION` |

### 9.3 Denegación uniforme

Cuando el principal **no tiene ninguna ruta establecida** hacia la company resuelta y no
presenta grant, la respuesta es exactamente
`{ decision: "DENY", reasonCodes: ["DENY_NOT_FOUND_UNIFORM"], obligations: [] }`,
indistinguible de un recurso inexistente. No revela existencia, empresa, ruta ni
ausencia de grant. Los códigos específicos solo se emiten a quien ya tiene una relación
legítima con la company.

---

## 10. Obligaciones

Una obligación acompaña un `ALLOW` condicionado o explica qué levantaría un `DENY`.
**Nunca** sustituye un grant.

`OBL_AUDIT_DECISION` · `OBL_BIND_RLS_COMPANY_CONTEXT` · `OBL_STEP_UP_REQUIRED` ·
`OBL_REASON_REQUIRED` · `OBL_POST_REVIEW_REQUIRED` · `OBL_SECOND_APPROVER_REQUIRED` ·
`OBL_AUDIT_HIGH_RISK_SIGNAL` · `OBL_REVALIDATE_BEFORE_READ` ·
`OBL_REVALIDATE_BEFORE_PUBLISH` · `OBL_PORTABILITY_SCOPE_ONLY`

Todo `ALLOW` emite `OBL_BIND_RLS_COMPANY_CONTEXT`: la autorización de aplicación fija el
contexto transaccional de company y RLS aplica la segunda defensa. Ninguna capa confía
en otra como única defensa.

---

## 11. Cobertura de pruebas

`spikes/FNC-SEC-001/` materializa **61 pruebas** con `node:test`, sin dependencias
externas y con datos exclusivamente sintéticos:

- los 7 casos positivos y 16 negativos de `TST-TEN-001` (`test/tenancy.test.mjs`);
- assurance insuficiente, SoD, finalidad incorrecta, estado desconocido, campo
  desconocido, señales de dispositivo e IP, operación unipersonal, estados de company y
  recurso, principales no humanos, pureza, inmutabilidad y garantía de no lanzar
  (`test/authorize.test.mjs`).

La suite se validó con un análisis de mutación de ocho mutantes sobre ramas críticas
(validación de entrada, confianza en el `company_id` del cliente, SoD, assurance,
`authorization_version`, denegación uniforme, operador primario y el `catch` de
seguridad). **Los ocho mutantes fueron detectados**, lo que da evidencia de que las
pruebas ejercitan realmente cada control y no solo el camino feliz.

---

## 12. Límites de v0 y pendientes

1. **No es autenticación.** El kernel no valida credenciales, tokens, firmas ni sesiones reales; recibe el resultado ya resuelto.
2. **No consulta almacenamiento.** Toda resolución server-side llega como entrada. La correcta resolución del `company_id` del recurso es responsabilidad de la capa que lo invoque y es el supuesto más fuerte del diseño.
3. **Persona ≠ subject.** Ver §6. Requiere decisión de identidad fuera de esta tarea.
4. **Sin jerarquía de recursos.** Un grant referencia tipos de recurso, no árboles ni instancias concretas. La granularidad por instancia queda pendiente.
5. **Sin delegación temporal ni «actuar como».** No modelado deliberadamente.
6. **Assurance como escala lineal.** `AAL1..AAL3` no distingue factores; una decisión sobre passkeys y step-up real corresponde a la tarea de identidad.
7. **`grant.issue` no está restringido por rango.** Falta la regla que impida a un principal emitir un grant más amplio que el suyo.
8. **RLS no está probada aquí.** Este spike cubre la capa de política. La segunda defensa en base de datos se prueba en su propia tarea.

Estos ocho puntos deben resolverse antes de convertir esta política en implementación
productiva. Ninguno se resuelve dentro del alcance de FNC-SEC-001.
