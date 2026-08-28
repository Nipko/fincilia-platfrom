# AWS T0 — control plane sintetico

Estado: **autorizado solo para control plane** · Tarea `FNC-PLT-010` · Región
`sa-east-1` · Expira 2026-09-27.

## Alcance del primer apply

El primer plan crea únicamente recursos sin runtime continuo: VPC y subredes, S3, ECR,
Cognito, roles IAM, CloudTrail, presupuesto y estado remoto. No crea EC2, RDS, NAT Gateway,
ALB, Fargate, KMS administrado por cliente ni Secrets Manager.

Esto permite validar el perímetro antes de consumir créditos ejecutando servidores. Todo
objeto y tag declara `synthetic_only`; no habilita DRG-00 ni modifica los gates legales.

## Autenticación y estado

- Operador: credenciales temporales emitidas por `aws login` en el perfil
  `fincilia-sandbox`; nunca access keys permanentes.
- Guard: el account ID esperado se inyecta localmente y otra cuenta falla antes del plan.
- Bootstrap: estado local sin secretos fuera del repositorio, con permisos del usuario.
- Estado principal: bucket S3 con SSE-S3, versionado, bloqueo público y lockfile nativo.

## Secuencia operativa

1. Validar cuenta Free activa y región por AWS CLI.
2. Ejecutar `tofu fmt`, `validate` y pruebas del contrato.
3. Aplicar solo el bucket de estado del bootstrap.
4. Inicializar T0 contra ese backend.
5. Guardar plan binario fuera del repositorio y convertirlo a JSON.
6. Ejecutar `python -m tools.aws_t0.validate --plan <plan.json>`.
7. Aplicar exactamente el plan validado; nunca ejecutar `tofu apply` sin archivo de plan.
8. Inventariar y registrar consumo/credits después del apply.

## Paso posterior, no incluido

Integrar adaptadores Cognito/S3/RDS, medir imágenes y memoria, producir una nueva estimación
y autorizar un plan distinto que habilite runtime. La cuenta no se convierte a Paid.
