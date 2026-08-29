---
id: FNC-PLT-014
title: Laboratorio efimero de actividades AWS Credits
status: review_pending
implementer: Codex principal dev + Integration Steward
base_sha: 880576d
gate: none
gate_effect: evidence_only
data_ceiling: synthetic_only
independent_reviewers: [Platform/SRE, Security]
---

# Resultado

Ejecutar de forma aislada las tres actividades adicionales del plan gratuito de
AWS y dejar un camino de retirada fail-closed. El laboratorio no despliega
Fincilia ni se reutiliza como infraestructura de beta o producción.

# Rutas

- Permitidas: `infra/aws/credit-lab`, esta ficha, su handoff y
  `CURRENT_PHASE.md` como Integration Steward.
- Prohibidas: producto API/web, migraciones, datos reales, secretos, tfstate,
  DRG-00/01, IaC de la beta y decisiones de arquitectura productiva.

# Invariantes

1. Sólo contenido sintético; ningún usuario o documento de Fincilia.
2. Lambda es mínima y su URL no recibe ni almacena entradas.
3. RDS permanece privado, cifrado, vacío y descartable sin snapshot.
4. Bedrock recibe una única petición sintética y no crea capacidad persistente.
5. No se crea AWS Organizations ni Control Tower.
6. La retirada exige cuenta exacta, etiquetas esperadas, nombres exactos y una
   bandera destructiva explícita.
7. No se retira el laboratorio hasta que AWS confirme los créditos o venza la
   ventana operativa documentada.

# Verificación

- Respuesta HTTPS de Lambda inspeccionada en navegador.
- Estado/configuración de RDS consultados mediante AWS CLI.
- Respuesta y métricas de Bedrock observadas en el playground.
- Sintaxis PowerShell y política sintética del repositorio.
- Estado de créditos observado antes y después.

# Fuera de alcance

Dominio, DNS, Cognito/Google, despliegue de Fincilia, datos reales, conexión a la
base, migraciones, promoción del laboratorio o aceptación de gates.

# Implementación integrada

- `c7ef06e`: Lambda sintética, contrato operativo y cleanup fail-closed.
- AWS confirmó USD 200 disponibles tras completar las cinco actividades.
- Cleanup aplicado y verificado: Lambda, rol IAM y RDS eliminados.
