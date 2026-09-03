# Activacion Google en UAT

Estado actual: **implementado y con control plane validado; no activado**.

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
  --tofu-dir infra/aws/t0 \
  --app-origin https://fincilia.com
```

La sonda descubre los selectores desde el estado remoto y solo emite 16
controles booleanos. No imprime pool, cliente, dominio administrado, secreto,
usuario ni correo. Un resultado `ok: true` prueba configuracion, no autorizacion:
`activation_authorized` y `real_data_authorized` permanecen falsos.

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
