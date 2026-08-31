# Publicación segura de imágenes del piloto privado

Este contrato separa tres operaciones que no deben confundirse:

1. construir y probar un candidato;
2. publicar sus tres imágenes inmutables por digest;
3. desplegar o activar el runtime.

FNC-SUP-003 implementa únicamente la segunda y vuelve a ejecutar las pruebas del
candidato en la misma ejecución que publica. No aplica OpenTofu, no cambia ECS,
no acepta gates y mantiene `FINCILIA_REAL_DATA_ENABLED=false`.

## Frontera de confianza

AWS confía exclusivamente en el `sub` inmutable del repositorio y el ambiente
GitHub `private-pilot`. La audiencia es `sts.amazonaws.com`. El workflow usa el
rol `fincilia-private-pilot-ecr-publisher` durante un máximo de una hora y no
recibe access keys permanentes.

El ambiente GitHub debe configurarse fuera del repositorio con `main` como rama
permitida y protección humana. El rol ARN se publica como output de OpenTofu y se
configura en la variable de ambiente
`AWS_PRIVATE_PILOT_PUBLISH_ROLE_ARN`; no es un secreto.

## Ejecución prevista

El operador abre `Publish immutable private-pilot images`, ingresa un SHA de 40
caracteres alcanzable desde `main` y escribe `PUBLISH`. El job:

- verifica el commit antes de ejecutar su contenido;
- construye API, worker y web y ejecuta sus pruebas/smoke tests;
- crea dos veces el bundle determinista y valida que no deriva;
- obtiene una sesión AWS temporal por OIDC y confirma cuenta/región;
- publica las tres imágenes con el SHA completo como tag;
- resuelve los tres digests desde ECR, espera los escaneos y rechaza cualquier
  resultado no completo o con vulnerabilidades críticas;
- atesta bundle, SBOM y cada digest, verifica las attestations y emite un
  manifiesto canónico sin credenciales.

Un fallo parcial no despliega nada y no genera un manifiesto completo. Como ECR
usa tags inmutables, una repetición después de una publicación parcial puede
requerir un commit nuevo; las imágenes parciales se inventarían y no se borran
automáticamente.

## Bloqueos vigentes

- ADR-034 sigue `Proposed`.
- La fundación y el ambiente GitHub no se han aplicado/configurado.
- Security, QA y Platform/SRE no han realizado la revisión independiente.
- DRG-00 y DRG-01 permanecen `not_met`; no se permiten documentos reales.
