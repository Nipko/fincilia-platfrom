---
task_id: FNC-IAM-001
revision: R1
status: REVIEW_PENDING
base_sha: e67814d5c36952fc42f184f5960c232f2cbd1808
implementation_shas: [987778d]
tested_head_sha: 987778d
data_ceiling: synthetic_only
gate_effect: none
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Privacy/Legal, Architecture, QA]
---

# Handoff FNC-IAM-001-R1 — Google y cliente Cognito público

## Resultado

Google quedó registrado manualmente como proveedor social del User Pool sin
exponer su Client Secret. OpenTofu administra un cliente Cognito separado para
`fincilia.com`; el cliente histórico de localhost permanece intacto.

El cliente público no genera secret, usa Authorization Code, solicita solo
`openid email profile`, admite únicamente Google, revoca tokens y limita access
e ID tokens a 15 minutos. Sus únicas URLs son:

- callback: `https://fincilia.com/api/auth/callback/cognito`;
- logout: `https://fincilia.com/entrar`.

Google retorna a Cognito mediante el endpoint `/oauth2/idpresponse` del dominio
alojado. Google nunca recibe el callback interno de Fincilia y el navegador no
entrega claims de empresa o rol.

## Evidencia reproducible

- `python -m unittest tools.aws_t0.test_validate -v`: 25 pruebas, OK.
- `tofu fmt -check` y `tofu validate`: OK.
- Plan adjudicado: `1 to add, 0 to change, 0 to destroy`.
- Validador de plan T0: `{ "errors": [], "ok": true }`.
- Apply: un cliente creado; ningún cambio o eliminación.
- Lectura posterior AWS: Google único IdP, Code, scopes mínimos, callback/logout
  exactos, tokens de 15 minutos y revocación activa.
- Plan posterior: `No changes`.
- Quality gate sobre el índice del commit: sin hallazgos.

Los identificadores AWS y el Client ID Cognito se obtienen desde outputs o AWS y
no se versionan. El Client Secret de Google no pasó por chat, Git, plan, state,
logs del agente ni archivos del repositorio.

## Límite deliberado

La web pública actual continúa siendo la beta sintética y no recibe variables
OIDC. La API rechaza arrancar OIDC fuera del entorno `pilot` o sin una atestación
DRG-00 válida firmada por KMS. Por eso esta entrega prepara la federación pero no
permite iniciar sesión con una identidad real. DRG-00, Privacy/Legal, Security,
Architecture y QA continúan pendientes.

## Siguiente paso

Adjudicar DRG-00 con revisores independientes y una atestación KMS válida;
después desplegar el runtime `pilot`, inyectar los endpoints/Client ID desde
outputs y ejecutar `tools.identity_readiness` antes del primer login.

## Rollback

El recurso tiene `prevent_destroy`. Para retirarlo se requiere un cambio
explícito y revisado que elimine esa protección, plan de borrado aislado y
confirmación de que el runtime continúa deshabilitado. El cliente local y el
proveedor Google no se alteran al detener la activación.
