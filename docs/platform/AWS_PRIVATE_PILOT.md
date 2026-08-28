# AWS private pilot — entorno para datos propios

Este runbook describe `FNC-PLT-012`. El entorno es deliberadamente distinto de
`closed-beta`: no comparte VPC, stores, secretos, backups ni estado. Crear la
infraestructura no abre DRG-00/01 y no autoriza subir datos.

## Despliegue en dos fases

La fase **foundation** crea red, cifrado, stores, identidad, observabilidad,
secretos vacíos y definiciones de tareas con capacidad cero. Puede planificarse
con datos sintéticos para producir evidencia de arquitectura.

La fase **activation** solo ocurre después de poblar secretos fuera de OpenTofu,
validar ACM/DNS, configurar Google en Cognito y obtener las firmas de los gates.
Las aplicaciones verifican las firmas KMS al arrancar; una variable por sí sola
no habilita identidad ni documentos reales.

## Datos permitidos después de DRG-01

Una empresa propia del Founder, hasta tres usuarios nominales y únicamente
extractos, auxiliares y facturas CSV/XLSX/PDF. Se excluyen tarjetas, nómina,
identificaciones oficiales, salud, credenciales, conectores e IA externa.

## Entradas locales

- Cuenta AWS exacta y región `sa-east-1`.
- FQDN definitivo y prefijo Cognito.
- SHA completo e imágenes ECR por digest.
- ARN de SNS para alertas, si el concepto de privacidad autoriza el destino.
- Nombres de revisores independientes y referencias de evidencia; nunca
  secretos, correos, documentos o valores financieros.

Las variables sensibles viven en un `pilot.auto.tfvars` ignorado. Los valores de
Secrets Manager se cargan por un procedimiento interactivo que no imprime ni
versiona el contenido.

## Verificación estática

```text
python -m tools.aws_private_pilot.validate
python -m unittest tools.aws_private_pilot.test_validate
tofu -chdir=infra/aws/private-pilot fmt -check -recursive
tofu -chdir=infra/aws/private-pilot validate
```

Cuando exista un plan guardado:

```text
tofu -chdir=infra/aws/private-pilot show -json pilot.plan > pilot-plan.json
python -m tools.aws_private_pilot.validate --plan infra/aws/private-pilot/pilot-plan.json
```

No se ejecuta `apply` hasta revisar el plan, costo, DNS y bloqueos DRG. El
validator distingue contrato válido de gate cumplido.

## Respuesta a incidente y salida

Cerrar el listener/servicios, revocar sesiones e invitaciones, preservar
CloudTrail y delete ledger, rotar secretos y conciliar inventario con S3/RDS.
La destrucción ocurre solo después de verificar borrado, retención y backups;
no se usa un `destroy` improvisado como sustituto del procedimiento.
