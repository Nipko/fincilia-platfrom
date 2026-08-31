# ADR-034 — GitHub OIDC para publicar imágenes en ECR

- Estado: **Proposed; bloqueado por apply y revisión independiente**
- Fecha: 2026-08-30
- Tarea: FNC-SUP-003
- Gate: DRG-01

## Contexto

El candidato de release ya tiene procedencia y SBOM firmados mediante la
identidad OIDC de GitHub, pero sus imágenes no están en el registry del piloto.
Publicarlas con access keys de un usuario IAM crearía credenciales duraderas y
ampliaría innecesariamente el radio de fallo.

El repositorio público `Nipko/fincilia-platfrom` fue creado después del 15 de
julio de 2026. GitHub incluye por defecto los identificadores inmutables del
owner y del repositorio en `sub`; para este repositorio son `16093741` y
`1342497632`. El contexto de un job ligado al ambiente `private-pilot` es
`environment:private-pilot`.

## Decisión propuesta

La fundación AWS declarará el proveedor
`https://token.actions.githubusercontent.com` con audiencia
`sts.amazonaws.com` y un rol exclusivo de publicación ECR. La confianza exigirá
por igualdad, sin comodines, este sujeto:

`repo:Nipko@16093741/fincilia-platfrom@1342497632:environment:private-pilot`

El rol sólo podrá obtener el token de ECR, subir capas, registrar imágenes y
consultar el escaneo de los repositorios `api`, `web` y `worker` del piloto. No
podrá crear o borrar repositorios/imágenes, modificar IAM/KMS/ECS, ni asumir
otro rol.

Un workflow manual ligado al ambiente protegido `private-pilot` construirá,
probará y publicará las tres imágenes desde un SHA completo alcanzable desde
`main`. Cada tag será el SHA completo y el manifiesto de salida usará los
digests devueltos por ECR. El workflow generará attestations de esos digests y
fallará si el escaneo no termina o reporta vulnerabilidades críticas.

La publicación no modifica OpenTofu, ECS, DNS, gates ni banderas de datos. El
ambiente GitHub y la confianza AWS deben existir antes de ejecutar el workflow;
su creación es una operación externa separada y revisable.

## Consecuencias

- No se almacenan secretos AWS en GitHub.
- Renombrar o transferir el repositorio rompe la confianza, que es el fallo
  seguro esperado.
- Un release parcial puede dejar blobs o tags inmutables, pero nunca produce un
  manifiesto completo apto para desplegar.
- ECR conserva las imágenes según su lifecycle; publicarlas puede generar costo
  de almacenamiento y escaneo, aun con el runtime apagado.
- Security, QA y Platform/SRE deben revisar IaC, workflow y evidencia antes de
  considerar esta decisión aceptada.

## Alternativas descartadas

- Access keys de un IAM user: credenciales duraderas y rotación operativa.
- Rol confiado a todo el repositorio o a cualquier branch: un workflow nuevo o
  una rama no revisada podría publicar.
- Tags `latest` o de versión móviles: no identifican los bytes desplegados.
- Publicar y desplegar en el mismo job: mezcla supply chain con mutación del
  runtime y dificulta rollback y revisión.

## Rollback

Revocar la confianza del rol bloquea nuevas sesiones inmediatamente. Las
sesiones existentes expiran en una hora como máximo. Las imágenes ya publicadas
se mantienen inmutables hasta una purga explícita compatible con inventario y
retención; no se borran como parte del rollback automático.
