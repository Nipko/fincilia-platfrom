# Solicitud de decision — assurance de identidad Google federada

- ID: UD-IAM-FEDERATED-MFA
- Fecha: 2026-08-29
- Tarea bloqueada: FNC-IAM-003 / activacion nominal de FNC-IAM-001
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
  verificado, y enlaza la cuenta mediante invitacion nominal de un uso.
- La sesion Fincilia dura 15 minutos y la autorizacion se revalida server-side.
- AWS documenta que la autenticacion federada no usa los flujos configurados en
  el app client y delega los factores primario/MFA al IdP.
- El plano privado mantiene MFA `ON` para usuarios nativos y ahora cierra el
  `SignUp` nativo publico; ninguna de las dos propiedades prueba MFA Google.

## Opciones

| Opcion | Ventajas | Riesgos | Costo de reversion |
|---|---|---|---|
| A. Google para beta; assurance declarado como federado no verificable | Conserva UX, password fuera de Fincilia y beta por invitacion | No se puede prometer MFA; requiere limitar riesgo y pedir 2SV como norma operativa no verificable | Bajo; anadir step-up despues |
| B. Cognito nativo con TOTP obligatorio | MFA tecnicamente demostrable en Cognito | Reintroduce password, elimina el acceso Google simple y duplica recuperacion | Medio/alto |
| C. Google Workspace administrado con 2SV obligatoria | MFA gobernable en el dominio | Excluye cuentas personales/amigos y anade costo/administracion | Alto para esta beta |

## Recomendacion del agente

Opcion A para la beta cerrada: no afirmar MFA, exigir invitacion nominal, sesion
corta, cierre federado, revocacion de grants y recomendacion explicita de 2SV a
los testers. Antes de GA o acciones financieras de alto riesgo, decidir un
step-up verificable o una identidad empresarial administrada.

## Decision humana

- Estado: Proposed
- Aprobador: pendiente (Security + Product; `FOUNDER-01` puede decidir riesgo,
  pero no cuenta como revision independiente)
- Fecha: pendiente
- ADR o cambio requerido: adjudicar y actualizar ADR-012/DRG-00
