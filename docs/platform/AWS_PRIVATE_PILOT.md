# AWS private pilot — entorno para datos propios

Este runbook describe `FNC-PLT-012`. El entorno es deliberadamente distinto de
`closed-beta`: no comparte VPC, stores, secretos, backups ni estado. Crear la
infraestructura no abre DRG-00/01 y no autoriza subir datos.

## Ciclo de costo: frío por defecto

El piloto no permanece completamente encendido. `pilotctl.ps1` separa la
infraestructura persistente de la temporal:

| Modo | Conserva | Retira o mantiene detenido |
| --- | --- | --- |
| `cold` | VPC, S3, KMS, Cognito, secretos vacíos, ECR, rol GitHub OIDC de publicación, CloudTrail, backups y almacenamiento RDS | NAT, endpoints Interface, ALB/WAF, Valkey, tareas ECS; solicita detener RDS |
| `warm` | Todo lo anterior y el plano runtime | API y worker continúan con `desired_count=0` |

`warm` no es sinónimo de “aceptar usuarios o datos”. Sólo prepara la red y los
servicios administrados; la activación de tareas sigue separada y bloqueada por
DRG-00/01, secretos, migración, DNS/ACM y revisión independiente.

Mientras `certificate_ready=false`, `warm` crea la definición de tarea y el
servicio worker en cero, pero no crea el servicio de aplicación ni el listener
HTTPS. Esta dependencia evita registrar el target group en ECS antes de que
ACM tenga un certificado validado. No se abre un listener HTTP temporal: el
plano queda apto para ejecutar bootstrap y migraciones sin publicar tráfico.

Amazon RDS sólo permite detener una instancia durante siete días consecutivos;
después puede reiniciarla automáticamente. Por ello `status` siempre muestra
ese límite y el operador debe verificar/enfriar de nuevo antes del séptimo día.
El almacenamiento RDS, snapshots, S3, KMS, Secrets Manager, ECR, CloudTrail y
logs pueden seguir generando costo en `cold`; no se presenta como costo cero.

El presupuesto administrado es una alarma account-wide, no un límite duro. Se
mide antes de aplicar créditos, descuentos o reembolsos para que los créditos
no oculten la velocidad de consumo. Envía avisos al alcanzar 50 % y 80 % del
gasto real mensual y cuando el pronóstico supera 100 %. Hasta que las etiquetas
de asignación de costos hayan sido activadas y madurado en Billing, no se filtra
por tags: un filtro prematuro podría omitir recursos recién creados.

## Preparación local una sola vez

Desde PowerShell, en la raíz del repositorio:

```powershell
Copy-Item infra/aws/private-pilot/pilot.auto.tfvars.example infra/aws/private-pilot/pilot.auto.tfvars
$env:FINCILIA_PILOT_ACCOUNT_ID = "<ACCOUNT_ID>"
```

Editar `pilot.auto.tfvars` con cuenta, dominio, prefijo Cognito, release por SHA,
imágenes ECR por digest y buzón de alertas. El archivo está ignorado por Git y
no debe contener secretos. Los secretos de aplicación se cargan directamente
en Secrets Manager mediante un procedimiento distinto.

## Operación diaria

Todos los comandos validan la cuenta `--account-id`, el perfil
`fincilia-sandbox` y `sa-east-1`. `status` es de solo lectura:

```powershell
infra/aws/private-pilot/pilotctl.ps1 status
```

Antes del primer `apply`, ejecutar el preflight comercial de solo lectura:

```powershell
infra/aws/private-pilot/pilotctl.ps1 commercial-preflight
```

Si RDS todavía no existe, el resultado sólo permite continuar con un plan de
cuenta `PAID` y estado `ACTIVE`. El reporte no muestra saldo de créditos,
instrumentos de pago ni identificadores de cuenta. La restricción existe
porque el plan gratuito no permite materializar la retención de backup de 14
días exigida por este entorno. El controlador no reduce ese control y rechaza
el `apply` antes de escalar ECS o cambiar la protección del ALB.

Además de RDS, ECS, NAT, ALB y Valkey, `status` lee exclusivamente las
direcciones de propiedad mediante `tofu state list`. No obtiene `state pull`,
outputs ni valores. El reporte separa foundation y runtime, lista las
direcciones mínimas faltantes y mantiene `G00-ISOLATED-ENV` en `pending` aunque
ambos inventarios estén completos: todavía exige release admitida, repetición
del drill en el target y revisión independiente.

Antes de encender se genera un plan guardado y se somete al validador:

```powershell
infra/aws/private-pilot/pilotctl.ps1 plan-warm
infra/aws/private-pilot/pilotctl.ps1 warm -Apply
```

Al terminar la sesión de prueba:

```powershell
infra/aws/private-pilot/pilotctl.ps1 plan-cold
infra/aws/private-pilot/pilotctl.ps1 cold -Apply
infra/aws/private-pilot/pilotctl.ps1 status
```

Sin `-Apply`, `warm` y `cold` se rechazan antes de mutar AWS. `cold` escala ECS
a cero, desactiva de forma temporal la protección de borrado del ALB, aplica el
plan validado y solicita detener RDS. Si el plan o el apply falla antes de borrar
el ALB, intenta restaurar inmediatamente la protección. CloudTrail registra las
operaciones. Nunca se usa `tofu destroy` para este ciclo.

## Despliegue en dos fases

La fase **foundation** crea red, cifrado, stores, identidad, observabilidad y
secretos vacíos. También crea el proveedor GitHub OIDC y el rol mínimo que sólo
publica las tres imágenes ECR; no crea access keys. El plano runtime se solicita
con `warm` y nace con capacidad cero. Puede planificarse con datos sintéticos
para producir evidencia de arquitectura.

La publicación de imágenes se rige por
`docs/platform/AWS_IMAGE_PUBLICATION.md`. Es manual, usa el ambiente GitHub
`private-pilot` y produce digests y attestations, pero no aplica OpenTofu ni
escala ECS.

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
- Buzón operativo para las alertas ACTUAL y FORECASTED de AWS Budgets.
- Nombres de revisores independientes y referencias de evidencia; nunca
  secretos, correos, documentos o valores financieros.

Las variables locales viven en un `pilot.auto.tfvars` ignorado. Los valores de
Secrets Manager se cargan por un procedimiento interactivo que no imprime ni
versiona el contenido.

El orden seguro entre RDS y el runtime esta definido en
`DATABASE_BOOTSTRAP_AWS.md`: preparar secretos, ejecutar el job de roles,
ejecutar migraciones y mantener servicios en cero hasta los gates. El usuario
maestro administrado por RDS nunca se entrega a API, web, worker o migrador.

## Verificación estática

```text
python -m tools.aws_private_pilot.validate
python -m tools.aws_image_publication.cli validate
python -m unittest tools.aws_private_pilot.test_validate
python -m unittest tools.aws_image_publication.test_model
tofu -chdir=infra/aws/private-pilot fmt -check -recursive
tofu -chdir=infra/aws/private-pilot validate
```

Cuando exista un plan guardado:

```text
tofu -chdir=infra/aws/private-pilot show -json pilot.plan > pilot-plan.json
python -m tools.aws_private_pilot.validate --plan infra/aws/private-pilot/pilot-plan.json
python -m tools.aws_image_publication.cli validate --plan infra/aws/private-pilot/pilot-plan.json
```

No se activa capacidad de aplicación hasta revisar el plan, costo, DNS y
bloqueos DRG. El validator distingue contrato válido de gate cumplido.

## Respuesta a incidente y salida

Cerrar el listener/servicios, revocar sesiones e invitaciones, preservar
CloudTrail y delete ledger, rotar secretos y conciliar inventario con S3/RDS.
La destrucción ocurre solo después de verificar borrado, retención y backups;
no se usa un `destroy` improvisado como sustituto del procedimiento.
