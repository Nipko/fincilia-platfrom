# ADR-012 — IdP administrado, sujeto interno y registro por adaptador

- Estado: **Proposed; forma sintetica autorizada para FNC-ONB-002**
- Fecha: 2026-08-28
- Gate: S1-READY / DRG-00

## Contexto

Fincilia necesita que una persona pueda empezar desde la web, pero autorizacion y
tenancy dependen de un `subject_id` interno estable, no del correo ni de claims de
empresa emitidos por un tercero. El proveedor local actual solo existe para datos
sinteticos y se niega a arrancar junto a datos reales.

## Decision

La interfaz de registro depende de un adaptador de identidad. En un entorno real,
un IdP administrado verifica correo e identidad; Fincilia enlaza su `sub` a un
`subject_id` y resuelve membresias y empresas server-side. El producto no se vuelve
autoridad de passwords reales. En federacion social, los factores primario y MFA
se delegan a Google: el `mfa_configuration` del User Pool cubre usuarios nativos y
no demuestra por si mismo MFA para una sesion Google. Fincilia no afirma un nivel
de MFA que los claims minimos no prueban.

Local y AWS T1 pueden implementar el mismo recorrido con un adaptador sintetico,
restringido a `@demo.local`, `real_data_enabled=false` y sin proveedores externos.
Ese adaptador crea atomicamente sujeto, binding local, credencial derivada, firma y
membresia owner. Crear la primera company permanece en la transaccion separada de
FNC-ONB-001: una identidad no constituye por si sola una frontera financiera.

El rol de la API nunca recibe escritura directa sobre credenciales. El alta local
se expone mediante una funcion de base acotada, propiedad de un rol `NOLOGIN` sin
DDL, declarada para revision bajo DB-G03.

## Consecuencias

- El recorrido web se puede probar completamente en T1 sin correo o PII real.
- Ninguna cuenta creada por el adaptador local es portable a un entorno real.
- Cognito T0 continua `admin_create_user_only` hasta que otra tarea implemente y
  revise callback OIDC, verificacion, MFA, recuperacion y proteccion contra abuso.
- FNC-IAM-001 prepara Google mediante Cognito con Authorization Code + PKCE y
  scopes mínimos. Su activación real permanece bloqueada por DRG-00 y revisión
  independiente; BETA-01 no la habilita porque nombre y correo son PII.
- Activar datos reales mantiene bloqueado el proveedor local por construccion.
- Security y Architecture deben revisar el IdP definitivo antes de DRG-00.
- El piloto privado mantiene cerrado `SignUp` nativo. La garantia adicional para
  identidades Google queda en `FNC-IAM-003-FEDERATED-MFA.md`; hasta adjudicarla,
  correo verificado e invitacion nominal no se etiquetan como MFA.

## Alternativas descartadas

- Guardar passwords reales en PostgreSQL: contradice IAM-01 y amplia el radio de
  una fuga de base.
- Confiar en un `company_id` del IdP: convierte claims externos en autorizacion.
- Crear company dentro de la transaccion de identidad: mezcla admission con la
  frontera financiera y elimina la eleccion explicita de datos operativos.
