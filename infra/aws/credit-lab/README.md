# Laboratorio efímero para actividades AWS Credits

Este laboratorio aislado materializa las tres actividades adicionales del plan
gratuito sin utilizar la plataforma, usuarios, documentos ni datos financieros:

- una función Lambda con URL pública y respuesta HTML completamente sintética;
- una instancia RDS PostgreSQL vacía, cifrada, privada y sin backups retenidos;
- una única petición sintética a Amazon Nova Micro en el playground de Bedrock.

No es una arquitectura productiva, no habilita datos reales y no cambia
DRG-00/01. Bedrock no deja recursos persistentes. Lambda, su rol IAM y RDS llevan
`Purpose=aws-credit-activity` y `ExpiresAt=2026-08-31`.

## Estado seguro

```powershell
$env:FINCILIA_PILOT_ACCOUNT_ID = "<cuenta-autorizada>"
./infra/aws/credit-lab/creditlab.ps1 status
```

El controlador valida primero la cuenta mediante STS y sólo consulta los tres
identificadores exactos. No imprime credenciales ni el secreto administrado de
RDS.

## Retirada

Primero se confirma en **AWS Console Home → Explore AWS → Earn AWS credits** que
las tres actividades figuran como completadas. Después:

```powershell
./infra/aws/credit-lab/creditlab.ps1 cleanup -Apply
```

La limpieza vuelve a validar cuenta y etiquetas antes de eliminar los nombres
exactos. RDS se retira sin snapshot porque está vacío y sólo contiene datos
sintéticos. La eliminación de RDS es asíncrona: `deleting` es el resultado
esperado inicial.

## Evidencia 2026-08-29

- Lambda respondió por HTTPS con el HTML sintético esperado.
- RDS alcanzó `available`, `db.t4g.micro`, privado y cifrado.
- Nova Micro respondió a una petición sintética en 363 ms.
- Los créditos visibles subieron de USD 140 a USD 180 tras Lambda y RDS.
- La adjudicación de Bedrock puede tardar hasta 30 minutos según AWS.
