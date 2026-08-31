---
id: FNC-SUP-003
status: REVIEW_PENDING
base_sha: f15ae9cc128bbb5615dc6ce43b29ba4db7a6d976
implementation_sha: 37d390ca0a47fb634908bd30a384ef6a99642fcc
evidence_correction_sha: 2743b26385a30f103f4f344aef8410891f9d9448
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, QA, Platform/SRE]
---

# Handoff FNC-SUP-003 — publicación OIDC de imágenes ECR

## Resultado

Fincilia dispone de un workflow manual registrado por GitHub para construir,
probar, publicar, escanear y atestar las imágenes `api`, `web` y `worker` de un
commit exacto de `main`. AWS entrega una sesión OIDC temporal de hasta una hora;
no existen access keys persistentes ni permisos para desplegar, borrar imágenes,
alterar repositorios o modificar otra infraestructura.

La salida canónica exige las tres imágenes por digest, escaneo ECR `COMPLETE`,
cero hallazgos `CRITICAL` y bundles de attestation. Aun completa, declara
`deployable: false` y `real_data_authorized: false`.

## Fronteras de seguridad

- Sujeto OIDC exacto, sin comodines:
  `repo:Nipko@16093741/fincilia-platfrom@1342497632:environment:private-pilot`.
- Audiencia exacta `sts.amazonaws.com`; cuenta `632144225293`, región
  `sa-east-1` y sesión máxima de 3600 segundos.
- `ecr:GetAuthorizationToken` es la única acción global. Las nueve acciones de
  carga/lectura restantes se limitan a los tres ARN ECR del piloto.
- El workflow sólo admite `workflow_dispatch`, ambiente `private-pilot`, runner
  hospedado, SHA completo igual al commit de `main` que contiene el workflow y
  Actions externas fijadas a SHA completo.
- No contiene `apply`, actualización ECS, secretos AWS, datos reales ni
  aceptación de gates.

## Verificación

| Evidencia | Resultado |
| --- | --- |
| Pruebas focales publicación/control/política | 88 OK |
| Pruebas focales tras corrección DRG-01 | 107 OK |
| `tofu fmt -check` / `tofu validate` | OK |
| `pilotctl plan-cold -AccountId 632144225293` | 142 `create`, 11 `read`, validado, sin apply |
| `pilotctl status` | modo `cold`; base, cache, balanceador y servicios ausentes; cero NAT |
| Quality gate sobre cada índice Git | OK, cero hallazgos |
| Registro del workflow en GitHub | aceptado por `gh workflow view` |
| CI de corrección `33358386719` | `success`; políticas, PostgreSQL, API, worker, Chromium y Axe verdes |

El primer run, `33357761851`, detectó correctamente que el contrato AWS
ampliado había invalidado el hash de FNC-GAT-006. La suite PostgreSQL fue verde
y el run falló únicamente al adjudicar evidencia obsoleta. FNC-GAT-006-R2 liga
la fuente nueva y conserva 14 blockers, `DRG-00/01: not_met` y datos reales
denegados.

## Estado externo y pendientes

- No se aplicó OpenTofu y no existen recursos `private-pilot` en AWS.
- El ambiente GitHub `private-pilot` todavía devuelve 404; no tiene protección
  de `main` ni la variable `AWS_PRIVATE_PILOT_PUBLISH_ROLE_ARN`.
- No se publicaron imágenes ni se ejecutó este workflow.
- ADR-034 permanece `Proposed` y bloqueado por apply, protección del ambiente,
  revisión independiente y DRG-01.
- Antes de crear recursos se requiere autorización explícita del plan actual de
  142 altas; la autorización histórica de 27 o 139 recursos no cubre este plan.
- Security, QA y Platform/SRE deben revisar IaC, workflow y evidencia; el autor
  no cuenta como revisor independiente.

## Orden de activación posterior

1. Revisar y autorizar el plan actual de 142 altas.
2. Aplicar la fundación fría y comprobar outputs/estado sin calentar runtime.
3. Crear/proteger el ambiente GitHub `private-pilot` y cargar únicamente el ARN
   no secreto del rol publicador.
4. Ejecutar manualmente el publicador sobre el `HEAD` exacto y verificar sus
   tres digests, escaneos y attestations.
5. Mantener runtime apagado y datos reales denegados hasta cerrar los gates.

## Rollback

Antes del apply basta revertir FNC-SUP-003. Después del apply, revocar primero la
confianza del rol impide nuevas sesiones; las sesiones existentes expiran en una
hora. Las imágenes inmutables no se eliminan automáticamente y quedan sujetas a
inventario y retención.
