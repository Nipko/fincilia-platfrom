# ADR-012 — IdP administrado, sujeto interno y alta publica Google

- Estado: **Proposed; implementacion preparada para revision independiente**
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

El rol de la API nunca recibe escritura directa sobre credenciales o identidad
global. En el sistema administrado, el recorrido explicito `register` crea sujeto,
binding HMAC, firma, membresia owner y aceptaciones legales en una sola funcion
acotada propiedad de un rol `NOLOGIN`. Un recorrido `login` desconocido nunca
crea la cuenta. El alta publica se puede cerrar operativamente sin impedir el
ingreso de cuentas existentes.

## Consecuencias

- El recorrido web se puede probar completamente en T1 sin correo o PII real.
- Ninguna cuenta creada por el adaptador local es portable a un entorno real.
- Cognito mantiene `admin_create_user_only`: Fincilia no abre SignUp nativo ni
  almacena passwords reales. Los perfiles federados Google sí pueden registrarse
  publicamente mediante el flujo revisado de Fincilia.
- FNC-IAM-001/003/004 implementan Google mediante Cognito con Authorization Code
  + PKCE, scopes minimos, logout y alta versionada. Su activacion con personas
  reales permanece bloqueada por DRG-00 y revision independiente.
- Activar datos reales mantiene bloqueado el proveedor local por construccion.
- Security y Architecture deben revisar el IdP definitivo antes de DRG-00.
- El `SignUp` nativo permanece cerrado. Correo verificado y acceso social no se
  etiquetan como MFA; el assurance y el step-up previo a GA siguen en
  `FNC-IAM-003-FEDERATED-MFA.md`.

## Alternativas descartadas

- Guardar passwords reales en PostgreSQL: contradice IAM-01 y amplia el radio de
  una fuga de base.
- Confiar en un `company_id` del IdP: convierte claims externos en autorizacion.
- Crear company dentro de la transaccion de identidad: mezcla admission con la
  frontera financiera y elimina la eleccion explicita de datos operativos.
