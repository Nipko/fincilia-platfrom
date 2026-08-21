# Modelo de tenancy y cambio de firma v0

- Estado: Draftable
- Tarea: FNC-DOM-001
- ADR: ADR-003 (Accepted)
- Gate: S1-READY
- Datos permitidos: exclusivamente sintéticos
- Revisiones requeridas: Architecture, Accounting y Security

## 1. Propósito y alcance

Este modelo define la frontera entre administración, datos financieros y autorización. Su objetivo es que una `company` conserve identidad, histórico y evidencia aunque cambie la firma que la atiende.

El modelo cubre `subject`, `user_identity`, `organization`, `organization_membership`, `company`, `company_membership`, `engagement`, responsabilidades, `grant` y `service_principal`. No define todavía tablas, migraciones, roles finales ni contratos comerciales.

Los términos `organization` y `company` no son sinónimos de tenant:

- `organization` es un contenedor administrativo para equipo, billing y activos propios.
- `company` es la frontera financiera estable sobre la que se autoriza cada operación.
- `engagement` es una delegación revocable; nunca representa propiedad de la `company`.

## 2. Entidades

| Entidad | Identidad y función | No implica |
|---|---|---|
| `subject` | Persona lógica estable e independiente de sus credenciales. | Acceso por existir, por email o por pertenecer a una organización. |
| `user_identity` | Credencial OIDC, passkey u otro autenticador ligado a un único `subject`. | Que dos identidades con el mismo email sean el mismo `subject`. |
| `organization` | Firma, BPO o PYME que administra miembros, billing y activos administrativos propios. | Propiedad ni acceso financiero sobre una `company`. |
| `organization_membership` | Relación vigente entre un `subject` y una `organization`, con roles administrativos. | Acceso financiero a las empresas del portafolio. |
| `company` | Frontera financiera permanente de una entidad conciliada, a la que se vincula todo su histórico financiero. | Pertenencia a la firma actual; no contiene `firm_id`. |
| `company_membership` | Ruta de acceso directo entre un `subject` y una `company`. | Una capacidad efectiva sin un `grant` vigente. |
| `engagement` | Delegación de una `organization` hacia una `company`, con vigencia, alcance contractual y responsables. | Acceso implícito para la organización o todos sus miembros. |
| `engagement_responsibility` | Designación legal u operativa asociada a un engagement, por tipo y vigencia. | Autorización técnica. |
| `grant` | Autorización efectiva para principal, empresa, recurso, acción, finalidad y vigencia. | Acceso fuera de su ruta, finalidad o empresa. |
| `service_principal` | Principal no humano para integración, job o programación, con propietario administrativo explícito. | Acceso por ser propiedad de una organización o empresa. |
| `asset_ownership` / `asset_license` | Titularidad y licencia de plantillas, recetas, reglas u otros activos compartibles. | Responsabilidad legal o permiso de lectura/uso. |

Los identificadores son opacos, inmutables y no reutilizables. Emails, nombres, NIT u otros atributos descriptivos no forman la identidad ni una clave de autorización.

## 3. Cardinalidades

| Relación | Cardinalidad | Restricción |
|---|---|---|
| `subject` — `user_identity` | `1 : 0..N` | Cada identidad pertenece exactamente a un subject; un subject puede existir antes de registrar una credencial. |
| `subject` — `organization` | `N : M` mediante `organization_membership` | Cada membership referencia exactamente un subject y una organization. Puede haber varias relaciones históricas, pero no dos memberships vigentes equivalentes para el mismo par y contexto. |
| `subject` — `company` | `N : M` mediante `company_membership` | Es la ruta directa de la PYME; no depende de una firma. Cada membership referencia exactamente un subject y una company. |
| `organization` — `company` | `N : M` mediante `engagement` | Una company puede tener cero, uno o varios engagements concurrentes o históricos. Cada engagement pertenece exactamente a una organization y una company. |
| `engagement` — `engagement_responsibility` | `1 : 0..N` | Las responsabilidades tienen tipo, responsable y vigencia explícitos. |
| Principal — `grant` | `1 : 0..N` | Un grant tiene exactamente un principal: un `subject` o un `service_principal`, nunca ambos. |
| `company` — `grant` | `1 : 0..N` | Todo grant referencia exactamente una company, aunque el recurso tenga identificador global. No hay grants financieros sin `company_id`. |
| Ruta de acceso — `grant` | `1 : 0..N` | Un grant humano referencia exactamente una ruta: `company_membership` directa o `organization_membership + engagement` delegada. |
| Propietario administrativo — `service_principal` | `1 : 0..N` | Cada service principal tiene exactamente un propietario administrativo, `organization` o `company`; la propiedad no le concede capacidades. |
| `company` — operador primario | `1 : 0..1` activo | Como máximo un engagement activo puede ser `primary_accounting_operator` para esa company. |

Puede haber varios engagements activos para asesoría, auditoría o transición. La exclusividad aplica al operador contable primario con capacidad delegada de escritura/cierre, no a toda colaboración ni a los aprobadores directos de la empresa.

## 4. Estados y transiciones

Todas las transiciones registran actor, instante UTC, motivo, versión de autorización y correlación de auditoría. Los intervalos son semiabiertos: `valid_from <= now < valid_until`; un `valid_until` ausente no sustituye una revocación.

| Registro | Estados v0 | Transiciones y efecto de autorización |
|---|---|---|
| `subject` | `active`, `suspended`, `deactivated` | `suspended` deniega mientras persiste; `deactivated` es terminal y conserva referencias históricas. |
| `user_identity` | `pending`, `active`, `disabled`, `revoked` | Solo `active` autentica. Revocar una identidad no elimina el subject ni sus eventos. |
| `organization` | `active`, `suspended`, `closed` | `suspended` impide nuevas acciones delegadas; `closed` es terminal y no elimina engagements ni histórico. |
| `organization_membership` | `invited`, `active`, `suspended`, `revoked`, `expired` | Solo `active` dentro de vigencia satisface la ruta delegada. `revoked` y `expired` no se reactivan; se crea otra relación. |
| `company` | `onboarding`, `active`, `suspended`, `closed` | Las políticas de cada acción determinan si `onboarding` admite operaciones. `suspended` y `closed` deniegan nuevas mutaciones financieras; la lectura legal debe tener grant y política explícitos. El histórico no se elimina. |
| `company_membership` | `invited`, `active`, `suspended`, `revoked`, `expired` | Solo `active` dentro de vigencia puede sustentar un grant directo. |
| `engagement` | `draft`, `pending_acceptance`, `active`, `frozen`, `revoked`, `expired` | Solo `active` sustenta operaciones normales. `frozen` admite únicamente las acciones de lectura/portabilidad enumeradas en el grant y contrato. `revoked` es terminal. |
| `grant` | `pending`, `active`, `suspended`, `revoked`, `expired` | Solo `active`, vigente y compatible con toda la ruta autoriza. No existe reactivación de un grant revocado/expirado. |
| `service_principal` | `active`, `suspended`, `revoked` | Solo `active`, con credencial válida y grant vigente, puede operar. `revoked` es terminal. |

Transiciones permitidas del engagement:

~~~text
draft -> pending_acceptance -> active -> frozen -> revoked
                            |         |          -> active
                            |         -> revoked
                            -> revoked
active|frozen|pending_acceptance -> expired  (al vencer valid_until)
~~~

Volver de `frozen` a `active` exige al titular autorizado, motivo auditable, nueva evaluación de grants e incremento de `authorization_version`. Un engagement revocado no se revive: una nueva relación contractual crea otro `engagement_id`.

## 5. Invariantes

### 5.1 Frontera y pertenencia

1. Todo registro financiero tiene `company_id NOT NULL`; no se infiere desde `organization_id`, engagement, sesión ni input del cliente.
2. `company` no contiene `firm_id`, `owner_organization_id` ni otra referencia que la convierta en hija de una firma.
3. Crear, aceptar o activar un engagement no crea memberships ni grants y no da acceso por sí mismo.
4. Ser `Organization Owner`, `Firm Admin`, dueño de billing o propietario de un activo no concede acceso financiero.
5. El portafolio de una firma es una proyección recalculada de engagements y grants vigentes, no una colección de companies poseídas.
6. Revocar o transferir un engagement no cambia el `company_id`, no mueve registros y no reescribe evidencia, decisiones, auditoría ni linaje.

### 5.2 Autorización

1. Toda decisión se resuelve server-side usando el principal autenticado y el recurso resuelto por el servidor. Un `company_id` enviado por cliente es solo una solicitud no confiable.
2. Membership o engagement son precondiciones de ruta; el permiso efectivo siempre requiere un grant vigente.
3. Cada grant restringe `company_id`, principal, ruta de acceso, recurso, acción, finalidad, vigencia y nivel de assurance mínimo.
4. Un grant delegado referencia el engagement que lo sustenta. No puede reutilizarse mediante otro engagement de la misma organización.
5. Un grant directo referencia la company membership que lo sustenta. No sobrevive a su suspensión, revocación o expiración.
6. Denegación, SoD y límites de estado prevalecen sobre cualquier allow. Un dato faltante, estado desconocido o versión obsoleta produce `DENY`.
7. No existen grants cross-company ni comodines que omitan `company_id`. Una vista consolidada recalcula el conjunto autorizado empresa por empresa.
8. RLS, objetos, colas, workers, caché, informes y proyecciones reciben el company scope ya autorizado y aplican una segunda defensa; ninguno amplía el grant.

### 5.3 Operador contable primario

1. Una company puede tener cero o un `primary_accounting_operator` activo; la designación recae en un engagement, no en una organization de forma global.
2. Solo el engagement designado puede recibir grants delegados para `financial_write`, `close.prepare`, `close.approve` o `close.reopen`.
3. La designación no concede acciones: cada sujeto o service principal necesita su propio grant.
4. Activar una segunda designación incompatible se rechaza de forma atómica; nunca se corrige el conflicto por orden de lectura.
5. Los miembros directos de la company pueden conservar grants de aprobación o supervisión sin convertirse en un segundo operador primario, siempre sujetos a SoD.
6. La misma persona no prepara y aprueba el mismo control financiero. Pertenecer a la firma primaria no elimina esta restricción.

### 5.4 Separación de dimensiones

| Dimensión | Registro autoritativo | Pregunta que responde | Efecto sobre autorización |
|---|---|---|---|
| Responsabilidad legal/contractual | `engagement_responsibility` y referencia contractual | ¿Quién responde y bajo qué rol/vigencia? | Ninguno por sí solo. |
| Propiedad de activo | `asset_ownership` | ¿Quién es titular de la plantilla, receta o regla? | Ninguno por sí solo. |
| Licencia de activo | `asset_license` | ¿Quién puede usar/exportar un activo y bajo qué condiciones? | No permite leer datos financieros sin grant. |
| Responsabilidad operativa | assignment/responsibility tipada | ¿Quién prepara, revisa o coordina? | Es atributo de política; no reemplaza el grant. |
| Autorización | `grant` + ruta vigente + políticas | ¿Puede este principal ejecutar esta acción ahora y con esta finalidad? | Es la única base de allow efectivo. |

Ningún campo genérico `owner` puede representar más de una dimensión. La responsabilidad legal, el titular del dato o activo, el operador primario y el principal autorizado pueden ser personas u organizaciones distintas.

## 6. Regla de autorización

### 6.1 Evaluación humana

~~~text
ALLOW(subject, resource, action, purpose) =
  subject.status == active
  AND authenticated_identity.status == active
  AND session is active and not revoked
  AND assurance >= policy.minimum_assurance
  AND server_resolved_company.status permits action
  AND active grant matches:
        subject + company + resource + action + purpose + time
  AND (
        active direct company_membership referenced by grant
        OR (
             active organization_membership referenced by grant
             AND active engagement referenced by grant
             AND membership.organization_id == engagement.organization_id
             AND engagement.company_id == grant.company_id
           )
      )
  AND grant.authorization_version == current company authorization_version
  AND no explicit deny, SoD conflict, legal hold restriction or state restriction
~~~

Para un engagement `frozen`, la condición `active engagement` se sustituye solo para acciones contractuales allowlisted como `portability.read` o `portability.export`. Mutaciones, creación de grants, jobs nuevos, webhooks y schedules se deniegan.

### 6.2 Evaluación no humana

Un service principal debe estar activo, autenticarse con credencial no revocada y presentar un grant exacto. Además:

- Si es propiedad administrativa de una company, el grant solo puede usar la ruta directa de esa company.
- Si actúa por una organization, el grant referencia un engagement activo de esa organization y company.
- Un job lleva `company_id`, `requested_by` y `authorization_version`; el worker revalida antes de leer y antes de publicar/confirmar resultados.
- Una capability para una empresa no puede reutilizarse en otra cola, objeto, cache key o proyección.

### 6.3 Secuencia server-side

1. Autenticar identidad o credencial y resolver el principal estable.
2. Resolver el recurso y su `company_id` desde almacenamiento autoritativo; no copiar el alcance desde el body, header o query string.
3. Leer estados y vigencias actuales de principal, ruta y grant.
4. Comparar la versión de autorización y el assurance requeridos.
5. Aplicar acción, finalidad, estado, SoD y políticas explícitas.
6. Fijar el contexto transaccional de company para RLS y ejecutar con mínimo privilegio.
7. Revalidar versión antes de efectos diferidos o publicación; auditar allow o deny sin registrar datos sensibles.

## 7. `authorization_version` e invalidación

Para v0, cada company mantiene un entero monotónico `authorization_version`. Todo contexto de sesión para company, job, enlace, webhook, schedule, export programado y namespace de caché se emite con la versión observada. La base autoritativa, no la caché, decide la versión actual.

Una mutación que reduce o cambia acceso incrementa la versión de cada company afectada dentro de la misma transacción que modifica memberships, engagements o grants. La invalidación company-wide es deliberadamente fail-closed: otros principals legítimos deben refrescar su contexto, pero sus memberships y grants no se revocan.

Al congelar un engagement se suspenden o revocan sus grants normales. Solo puede conservarse un grant contractual de portabilidad preexistente y explícito; cualquier concesión excepcional posterior debe aprobarla un principal autorizado por una ruta directa de la company, no la firma congelada. Al revocar o expirar, se invalidan también esos grants de portabilidad.

El flujo de invalidación es:

1. Se impide emitir grants y efectos nuevos para la ruta saliente.
2. Se suspenden o revocan los grants vinculados según la regla de freeze/revocación anterior.
3. Se incrementa `company.authorization_version` atómicamente.
4. Los contextos de sesión de esa company deben recalcularse; un token anterior no basta.
5. Los jobs pendientes o en ejecución con versión anterior se rechazan/cancelan antes de leer o confirmar resultados; solo un principal aún autorizado puede reenviarlos.
6. Enlaces y exports dejan de funcionar por revalidación online, aunque su firma o TTL criptográfico no hayan vencido.
7. Webhooks y schedules vinculados se deshabilitan; no generan entregas nuevas.
8. Las cachés anteriores quedan fuera del namespace vigente. Un retraso de purga no restaura acceso porque la versión se comprueba contra la fuente autoritativa.
9. Un service principal dedicado al engagement se revoca y sus credenciales se rotan o destruyen. Uno compartido pierde grants, tokens y capabilities de esa ruta sin afectar engagements no relacionados.
10. Una transacción financiera iniciada bajo la versión anterior aborta antes del commit si la versión cambió.

La revocación no borra resultados históricos. Su visualización posterior requiere otra ruta y grant vigentes, y toda reemisión queda auditada.

## 8. Casos operativos

### 8.1 Acceso directo de la PYME

1. Un titular autorizado crea o acepta una `company_membership` directa para un subject.
2. Un aprobador distinto emite grants por company, acción, recurso y finalidad según política.
3. El subject entra a la company por la ruta directa, incluso si no existe firma o si todos los engagements están revocados.
4. Cambiar de firma no altera esta membership. Solo una decisión explícita sobre la ruta directa puede suspenderla o revocarla.

### 8.2 Firma delegada

1. La company y la organization aceptan un engagement con vigencia y alcance contractual.
2. La activación del engagement deja el acceso en cero.
3. Se asignan responsabilidades y, si aplica, se designa el engagement como operador primario.
4. Cada profesional necesita organization membership vigente y un grant individual ligado al engagement.
5. El acceso termina si falla cualquiera de estos elementos, aunque los demás sigan activos.

### 8.3 Cambio ordinario de firma

Ejemplo totalmente sintético: `company_c1` cambia de `firm_alpha` a `firm_beta`.

1. Un subject con ruta directa, assurance reforzado y grant `engagement.transfer.initiate` inicia la solicitud.
2. `engagement_alpha` pasa de `active` a `frozen`. Se deniegan nuevas mutaciones y se conserva solo lectura/portabilidad contractual explícita.
3. Se captura el estado de pendientes y se genera un paquete de portabilidad respetando ownership y licencias; los datos financieros permanecen en `company_c1`.
4. La firma saliente confirma entrega o vence el plazo controlado. La falta de confirmación no transfiere propiedad ni prolonga acceso indefinidamente.
5. `engagement_alpha` se revoca, sus grants/capabilities se invalidan y aumenta `company_c1.authorization_version`.
6. `engagement_beta` puede activarse, pero sigue sin acceso hasta recibir responsabilidades y grants explícitos. Antes de dar escritura/cierre, la designación de operador primario de Alpha debe haber terminado.
7. Los usuarios directos de `company_c1` actualizan su contexto y conservan sus grants; el histórico mantiene el mismo `company_id` y todas las transiciones quedan auditadas.

Durante una ventana de transición, Alpha puede estar `frozen` con lectura contractual y Beta `active` con preparación controlada. Nunca hay dos operadores primarios con capacidad delegada de escritura/cierre.

### 8.4 Revocación inmediata

Ante incidente, mandato del titular o fin contractual efectivo, no se espera el flujo de entrega para cortar acceso. Se revoca el engagement y se ejecuta la invalidación del apartado 7. El paquete de portabilidad puede producirlo después un principal directo o la nueva firma con grant; la firma revocada no recupera acceso por esta necesidad.

### 8.5 Cambios parciales

- Revocar una organization membership quita a ese subject todas las rutas delegadas que la usan, pero no revoca engagements de la organización ni afecta a otros subjects.
- Revocar un grant quita solo sus capacidades; membership y engagement pueden permanecer por otras finalidades.
- Suspender una credencial impide autenticación con ella; otra identidad del mismo subject sigue sujeta al estado del subject, sesión y grants.
- Transferir la propiedad/licencia de una receta no transfiere acceso a la company ni cambia su engagement.

## 9. TST-TEN-001 — pruebas sintéticas de tenancy

### 9.1 Fixture mínimo

El fixture usa únicamente identificadores y nombres sintéticos:

- Companies: `company_c1`, `company_c2`.
- Organizations: `firm_alpha`, `firm_beta`, `org_sme_c1`.
- Subjects: `subject_direct`, `subject_alpha_preparer`, `subject_alpha_approver`, `subject_beta_reviewer`, `subject_outsider`.
- Service principals: `sp_alpha_import_c1`, `sp_alpha_shared`.
- Engagements: `engagement_alpha_c1`, `engagement_beta_c1`, `engagement_alpha_c2`.

Cada caso crea su propio reloj, versiones y grants; no comparte estado mutable con otro caso.

### 9.2 Casos positivos

| ID | Preparación | Acción | Resultado esperado |
|---|---|---|---|
| TST-TEN-001-P01 | Subject, company membership y grant directo activos para `company_c1`. | Leer un recurso de C1 con la finalidad autorizada. | `ALLOW`; auditoría identifica ruta directa y C1. |
| TST-TEN-001-P02 | Membership de Alpha, engagement Alpha–C1 y grant delegado exacto activos. | Preparar una operación permitida de C1. | `ALLOW`; la ruta contiene membership, engagement y grant. |
| TST-TEN-001-P03 | Alpha es operador primario; Beta tiene engagement asesor activo y grant de lectura. | Alpha escribe y Beta lee el recurso permitido. | Ambas acciones autorizadas por separado; Beta no adquiere escritura/cierre. |
| TST-TEN-001-P04 | Engagement Alpha congelado con grant explícito `portability.export`. | Exportar el paquete contractual dentro de vigencia. | `ALLOW` solo para el alcance de portabilidad. |
| TST-TEN-001-P05 | Service principal activo con grant Alpha–C1, credencial y versión actuales. | Ejecutar job de C1 y publicar resultado en C1. | `ALLOW` tras revalidación inicial y previa a publicación. |
| TST-TEN-001-P06 | Se completa cambio Alpha→Beta y hay member/grant válidos de Beta. | Acceder al histórico preexistente de C1. | `ALLOW`; los registros conservan `company_c1` y linaje original. |
| TST-TEN-001-P07 | Se revoca Alpha; el subject directo conserva membership/grant y refresca contexto. | El subject directo accede a C1. | `ALLOW` con la nueva authorization version. |

### 9.3 Casos negativos y cross-tenant

| ID | Preparación/ataque | Acción | Resultado esperado |
|---|---|---|---|
| TST-TEN-001-N01 | Engagement Alpha–C1 activo, sin grant. | Miembro de Alpha intenta leer C1. | `DENY`; crear engagement no concede acceso. |
| TST-TEN-001-N02 | Organization Owner de Alpha sin grant financiero. | Intenta listar movimientos de C1. | `DENY`; rol administrativo no implica finanzas. |
| TST-TEN-001-N03 | Grant activo ligado a engagement revocado/expirado. | Intenta leer o mutar C1. | `DENY`; toda la ruta debe estar vigente. |
| TST-TEN-001-N04 | Grant de C1 y request manipulado con `company_id=company_c2`. | Intenta leer recurso de C2. | `DENY` en API y RLS; el servidor resuelve C2 desde el recurso. |
| TST-TEN-001-N05 | Grant delegado de Alpha–C1 y organization membership suspendida. | Intenta actuar en C1. | `DENY`. |
| TST-TEN-001-N06 | Engagement Alpha–C1 pasa a `frozen`. | Intenta mutar, crear job o emitir grant nuevo. | `DENY`; solo acciones de portabilidad allowlisted pueden continuar. |
| TST-TEN-001-N07 | Link, job y cache key emitidos antes de revocar Alpha. | Se usan después del incremento de versión. | Todos fallan cerrados; no hay lectura ni publicación desde caché. |
| TST-TEN-001-N08 | `sp_alpha_import_c1` tiene capability de C1. | Worker cambia payload o namespace hacia C2. | `DENY`; no lee, escribe ni publica en C2. |
| TST-TEN-001-N09 | Alpha ya es operador primario activo de C1. | Se intenta activar a Beta como segundo operador primario con write/close. | La escritura se rechaza atómicamente; permanece un único operador. |
| TST-TEN-001-N10 | Beta tiene ownership/licencia sobre una plantilla, sin grant financiero. | Intenta leer datos de C1. | `DENY`; ownership/licencia no autorizan finanzas. |
| TST-TEN-001-N11 | Grant válido para finalidad `audit.read`. | Se reutiliza para `close.approve` o exportación. | `DENY` por acción/finalidad. |
| TST-TEN-001-N12 | Dos credenciales comparten email sintético pero tienen subjects distintos. | Una intenta usar grants de la otra. | `DENY`; autorización usa `subject_id`, no email. |
| TST-TEN-001-N13 | Una consulta consolidada conserva en caché C1 y C2; el subject pierde C2. | Refresca el portafolio. | Solo retorna C1 tras recalcular el conjunto autorizado. |
| TST-TEN-001-N14 | Transacción/job inició con versión anterior; engagement se revoca antes del commit/publicación. | Intenta confirmar efectos. | Aborta sin efecto financiero publicado; queda evidencia técnica segura. |
| TST-TEN-001-N15 | Engagement Beta activo pero aún sin grants tras transferencia. | Miembro de Beta intenta entrar a C1. | `DENY`; activar la nueva relación no concede acceso implícito. |
| TST-TEN-001-N16 | `subject_outsider` presenta un `company_id` y resource ID válidos observados externamente. | Intenta lectura directa. | `DENY` uniforme, sin revelar existencia ni metadatos de C1. |

### 9.4 Aserciones de persistencia y auditoría

El escenario de transferencia debe probar además que:

- El conteo y los identificadores de registros financieros de C1 son iguales antes y después del cambio.
- Ningún registro cambia de `company_id` ni recibe `organization_id` como sustituto.
- El engagement y los grants revocados permanecen como histórico no efectivo.
- Cada transición produce un evento auditable con actor, motivo, tiempo y versión, sin PII ni datos financieros en logs de prueba.
- Las denegaciones se observan en API, RLS, objeto, worker, link, caché y proyección donde corresponda; ninguna capa confía en otra como única defensa.

## 10. Criterio de revisión del borrador

FNC-DOM-001 permanece en `Draftable` hasta que los owners humanos estén asignados y Architecture, Accounting y Security confirmen:

- que las responsabilidades contractuales descritas no se interpretan como autorización;
- que la exclusividad del operador primario y SoD reflejan el proceso contable aprobado;
- que la invalidación company-wide de v0 es compatible con jobs, enlaces, sesiones y caché;
- que TST-TEN-001 se materializa como pruebas automáticas positivas y negativas en las capas indicadas.

La aprobación de este documento no supera por sí sola S1-READY ni autoriza datos reales.
