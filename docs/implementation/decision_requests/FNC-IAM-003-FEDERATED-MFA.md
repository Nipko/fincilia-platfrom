# Solicitud de decision — assurance de identidad Google federada

- ID: UD-IAM-FEDERATED-MFA
- Fecha: 2026-08-29
- Tarea bloqueada: assurance de FNC-IAM-003 / activacion externa de FNC-IAM-004
- Owner requerido: Security + Product
- Gate afectado: DRG-00
- Fecha limite: antes de habilitar `FINCILIA_OIDC_ENABLED` con personas reales

## Contradiccion o incertidumbre

El contrato decia que `mfa_configuration = ON` demostraba MFA para Google. En
federacion, Cognito delega los factores primario y MFA al IdP externo; los
scopes minimos `openid email profile` no aportan a Fincilia una prueba portable
de que una cuenta Google concreta uso segundo factor. Mantener esa frase daria
una garantia de seguridad no demostrable.

## Evidencia disponible

- La implementacion obliga Code + PKCE, state, nonce, issuer/audience y correo
  verificado. `login` nunca crea filas; `register` crea la identidad interna
  solo tras aceptar las versiones legales activas.
- La sesion Fincilia dura 15 minutos y la autorizacion se revalida server-side.
- AWS documenta que la autenticacion federada no usa los flujos configurados en
  el app client y delega los factores primario/MFA al IdP.
- El plano privado mantiene MFA `ON` para usuarios nativos y ahora cierra el
  `SignUp` nativo publico; ninguna de las dos propiedades prueba MFA Google.

## Opciones

| Opcion | Ventajas | Riesgos | Costo de reversion |
|---|---|---|---|
| A. Google público; assurance declarado como federado no verificable | Conserva UX y password fuera de Fincilia sin una infraestructura transitoria de invitaciones | No se puede prometer MFA; las acciones de alto riesgo necesitan límites o step-up posterior | Bajo; añadir step-up después |
| B. Cognito nativo con TOTP obligatorio | MFA tecnicamente demostrable en Cognito | Reintroduce password, elimina el acceso Google simple y duplica recuperacion | Medio/alto |
| C. Google Workspace administrado con 2SV obligatoria | MFA gobernable en el dominio | Excluye cuentas personales/amigos y anade costo/administracion | Alto para esta beta |

## Recomendacion del agente

Opcion A para el alta pública definitiva: no afirmar MFA, mantener sesión corta,
cierre federado y revocación server-side de membresías. La invitación no es un
factor de autenticación y se retira del diseño. Antes de habilitar acciones
financieras de alto riesgo se debe adjudicar un step-up verificable o una
identidad empresarial administrada.

## Decision humana

- Estado: Proposed para assurance/step-up; la apertura pública sin invitaciones
  fue aceptada por `FOUNDER-01` en IMP-020.
- Aprobador: pendiente para assurance (Security; `FOUNDER-01` no cuenta como
  revisión independiente)
- Fecha: pendiente
- ADR o cambio requerido: adjudicar assurance en ADR-012 antes de acciones de
  alto riesgo; DRG-00 continúa sin cambios.
