---
id: FNC-SUP-003
status: REVIEW_PENDING
base_sha: 2feb932ea0034dcf41a5e4af2cc5b9deaf3d95c2
publication_run: 33829236618
data_ceiling: synthetic_only
gate_effect: evidence_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, QA, Platform/SRE]
---

# Handoff FNC-SUP-003 R2 — imágenes vigentes del piloto privado

## Resultado

El workflow manual publicó API, web y worker desde el SHA completo
`2feb932ea0034dcf41a5e4af2cc5b9deaf3d95c2`. La corrida reconstruyó los tres
artefactos, ejecutó las pruebas dentro de sus contenedores, reprodujo el bundle,
verificó SLSA/SPDX, obtuvo una sesión AWS temporal mediante OIDC, publicó tags
inmutables, esperó los escaneos ECR y atestó cada digest.

| Componente | Digest ECR | Escaneo |
| --- | --- | --- |
| API | `sha256:211f9bf8af7de687ffc20d797668734b58ffa29c10cab9fadafb7d441d0aae17` | `COMPLETE`, 0 critical/high/medium/low |
| Web | `sha256:293e919944a5406653038beda640a105127f132a11d535f2a5b647e3d2adcd2a` | `COMPLETE`, 0 critical/high/medium/low |
| Worker | `sha256:9b957506421041722338512fc2bb86e9dc527891d9a0add6e7f9c80f5269b08c` | `COMPLETE`, 0 critical/high/medium/low |

La configuración local ignorada de OpenTofu referencia estos tres digests y el
SHA exacto; ningún secreto, token ni salida extensa de attestation se incorporó
al repositorio.

## Límites preservados

El manifiesto canónico conserva `deployable: false` y
`real_data_authorized: false`. Esta publicación no levantó RDS, ECS, NAT,
balanceador ni cache; tampoco aceptó un gate. La revisión independiente de
Security, QA y Platform/SRE continúa pendiente.

La corrida `33829205396` usó un SHA de entrada mal transcrito y falló en el
primer control de operador, antes de compilar o solicitar credenciales AWS. La
corrida definitiva `33829236618` terminó verde en 7m05s.

## Rollback

Las imágenes son inmutables y no se eliminan automáticamente. Para no usarlas,
se restablecen los digests anteriores en la configuración local; cualquier
despliegue posterior debe referenciar el digest, nunca el tag.
