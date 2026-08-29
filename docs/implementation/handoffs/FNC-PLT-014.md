---
id: FNC-PLT-014
status: REVIEW_PENDING
base_sha: 880576d
web_fix_sha: 824c687
lab_sha: c7ef06e
data_ceiling: synthetic_only
author: Codex principal dev + Integration Steward
independent_reviewers: [Platform/SRE, Security]
---

# Handoff FNC-PLT-014 — laboratorio efímero AWS Credits

## Resultado

Se completaron las tres actividades pendientes sin desplegar Fincilia ni usar
datos reales. AWS elevó el saldo visible de USD 140 a USD 200:

1. Lambda sirvió por HTTPS una página estática sintética.
2. RDS PostgreSQL alcanzó `available`, privado, cifrado y vacío.
3. Nova Micro respondió a una petición sintética desde Bedrock Playground.

El laboratorio quedó gobernado por `creditlab.ps1`, que valida la cuenta vía
STS y exige tanto `Purpose=aws-credit-activity` como nombres exactos antes de
eliminar. No se creó Organizations, Control Tower ni capacidad aprovisionada de
Bedrock.

## Evidencia

| Verificación | Resultado |
| --- | --- |
| URL pública Lambda | HTML sintético esperado, sin entrada ni persistencia |
| RDS | `available`, `db.t4g.micro`, privado, cifrado, secreto administrado activo |
| Bedrock | Amazon Nova Micro, 13 tokens de entrada, 17 de salida, 363 ms |
| Créditos | USD 140 → USD 180 → USD 200 visibles en AWS Console Home |
| `creditlab.ps1 status` | cuenta verificada, Lambda `Active`, RDS `available`, rol exacto |
| parser PowerShell | sintaxis OK |
| Lambda Python | compilación y contrato de respuesta OK |
| quality gate | OK sobre el índice Git |
| E2E visual relacionado | 1 Chromium, OK; corrige destino público obsoleto |

## Retirada aplicada

Después de confirmar USD 200 se ejecutó `cleanup -Apply`:

- Lambda: `deleted`;
- rol IAM: `deleted`;
- RDS vacío: `deleting` sin snapshot ni backups automatizados;
- Bedrock: cero recursos persistentes.

La eliminación de RDS es asíncrona. Una comprobación posterior debe confirmar
`DBInstanceNotFound`; no se recrea el laboratorio para obtener esa evidencia.

## Límites y revisión

- Esto no es infraestructura de beta, piloto o producción.
- No modifica DRG-00/01 ni autoriza información financiera real.
- No valida RDS como decisión productiva ni Bedrock como componente de Fincilia.
- Platform/SRE y Security deben revisar controlador, tags y evidencia.

## Rollback

El laboratorio ya fue retirado. Revertir los commits sólo elimina su contrato y
controlador del repositorio; no recrea recursos AWS. No debe volver a ejecutarse
la actividad con el único fin de duplicar créditos.
