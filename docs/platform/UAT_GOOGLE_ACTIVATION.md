# Activacion Google en UAT

Estado actual: **implementado; control plane objetivo 12/16; no activado**.

El recorrido definitivo ya separa login y registro, usa Authorization Code con
PKCE, valida `state` y `nonce`, acepta terminos y privacidad versionados, crea la
cuenta de forma atomica y mantiene PostgreSQL como autoridad de roles. Cognito
tiene SignUp nativo cerrado y el cliente publico no contiene secreto.

## Comprobacion redactada

Desde WSL, con la sesion temporal AWS activa:

```text
python3 -m tools.identity_readiness.cli \
  --profile fincilia-sandbox \
  --region sa-east-1 \
  --tofu-dir infra/aws/private-pilot \
  --app-origin https://fincilia.com
```

La sonda descubre únicamente el output `cognito` del estado remoto y emite 16
controles booleanos. No imprime pool, cliente, dominio administrado, secreto,
usuario ni correo. Un resultado `ok: true` prueba configuracion, no autorizacion:
`activation_authorized` y `real_data_authorized` permanecen falsos.

En la observación del 4 de septiembre de 2026 pasan 12 controles. Los cuatro
pendientes son exactamente el proveedor soportado, credenciales presentes,
scopes mínimos y mapeo de atributos de Google. El resto de la frontera —incluido
PKCE/code, callbacks, tokens cortos, revocación y cierre de SignUp nativo— pasa.

## Por que el boton aun no aparece

`fincilia.com` ejecuta el runtime UAT economico con identidad sintetica. El
runtime que contiene la frontera administrada de secretos, identidad de carga y
atestacion KMS es el plano separado de `infra/aws/private-pilot`. El contrato de
aplicacion rechaza OIDC si no existe una atestacion KMS de DRG-00.

Para activar sin relajar controles faltan:

1. materializar y ensayar `G00-ISOLATED-ENV` en el entorno objetivo;
2. revisión nominal independiente de Legal/Privacy sobre tratamiento y retencion;
3. revisión nominal independiente de Architecture/Security sobre region;
4. dictamen consolidado de Legal y Security, distintos de `FOUNDER-01`;
5. emitir la atestacion KMS DRG-00 y desplegar el artefacto inmutable aprobado.

No se debe copiar un client secret al repositorio, chat, terminal compartida o
archivo `.tfvars`. El alta se puede volver a cerrar fijando
`FINCILIA_OIDC_REGISTRATION_MODE=disabled` sin impedir login de cuentas ya
existentes.
