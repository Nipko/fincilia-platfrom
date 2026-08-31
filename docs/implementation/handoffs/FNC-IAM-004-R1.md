---
id: FNC-IAM-004-R1
status: REVIEW_PENDING
base_sha: 579b38178b77c888b983f5c0f93a858c0c2c9c88
data_ceiling: synthetic_only_until_DRG_00
---

# Corrección live de identidad Google/Cognito

## Hallazgo reproducido

La sonda live se ejecutó contra el cliente público Google exacto de Fincilia.
Pasaron 15 de 16 controles. El único fallo fue `IAM-LIVE-01`: el User Pool
tenía `DeletionProtection=INACTIVE`, aunque el resto del recorrido público
(PKCE, callbacks, scopes, Google, revocación, tiempos y SignUp nativo cerrado)
estaba correctamente configurado.

## Corrección

El recurso versionado activa `deletion_protection = "ACTIVE"` y añade
`prevent_destroy = true`. Ninguno de estos cambios activa el runtime, crea
usuarios, concede roles, modifica datos o mueve DRG-00/DRG-01.

## Evidencia ejecutada

- 39 pruebas focales de contrato T0 e identidad: OK.
- `tofu fmt -check` y `tofu validate`: OK.
- Plan adjudicado: cero altas, una actualización in-place y cero
  destrucciones; el validador estructural rechazará cualquier otro campo.
- Apply AWS: `DeletionProtection INACTIVE -> ACTIVE`, sin reemplazo.
- Sonda live posterior: 16/16 controles pasan; el informe no contiene
  identificadores personales ni secretos.

## Activación todavía separada

El control plane está listo, pero el runtime UAT económico sigue aislado de
Google por construcción: usa MinIO y SSM, mientras la configuración de producto
exige `pilot`, Secrets Manager, workload identity y atestación KMS. La siguiente
rebanada debe activar `infra/aws/private-pilot`; no se relajará esa frontera para
forzar OIDC sobre el host sintético. `FINCILIA_REAL_DATA_ENABLED` permanece
`false`.

## Revisiones

Security y Platform/SRE continúan siendo revisores independientes. Esta
corrección técnica no reemplaza su dictamen ni autoriza información real.
