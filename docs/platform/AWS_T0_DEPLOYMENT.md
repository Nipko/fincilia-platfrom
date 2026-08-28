# AWS T0 — control plane sintetico

Estado: **aplicado; revisión independiente pendiente** · Tarea `FNC-PLT-010` · Región
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

## Resultado del 2026-08-28

- Bootstrap: 8 recursos creados y plan posterior sin cambios.
- Control plane: 45 recursos creados y plan posterior sin cambios.
- CloudTrail registra management events, valida logs y no reporta error de entrega.
- Cognito exige MFA, impide autorregistro y conserva cero usuarios hasta el enrolamiento.
- Los tres repositorios ECR usan tags inmutables, AES-256 y scan on push.
- El bucket de objetos y el de auditoría son privados, versionados, cifrados y tienen
  lifecycle acotado; el estado principal existe versionado y cifrado en S3.
- El presupuesto bruto mensual es USD 5 y excluye créditos del cálculo para revelar el
  consumo real antes del beneficio promocional.
- Inventario negativo directo: 0 EC2, 0 RDS, 0 NAT Gateway, 0 load balancers y 0 ECS.

No se versionan account ID, ARNs, IDs de recursos, outputs locales ni estado. La evidencia
reproducible está en el handoff, mientras que los valores operativos permanecen en el
backend de OpenTofu y en AWS.

## Paso posterior, no incluido

Integrar adaptadores Cognito/S3/RDS, medir imágenes y memoria, producir una nueva estimación
y autorizar un plan distinto que habilite runtime. La cuenta no se convierte a Paid.
