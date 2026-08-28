---
task_id: FNC-PLT-011
status: REVIEW_PENDING
base_sha: 6a6822b
runtime_release_sha: a710c9e421852a54e35613de81f025fe3c533efc
integration_sha: 7fd1273
data_ceiling: synthetic_only
implemented_by: Codex principal dev + Integration Steward
independent_reviewers: [Security, Architecture, Platform, QA]
---

# Handoff FNC-PLT-011

## Resultado entregado

Fincilia ejecuta su plataforma web completa en un laboratorio AWS T1 temporal de un
solo host en `sa-east-1`. El host no tiene ingress, SSH ni key pair: el acceso humano
es exclusivamente un tunel de Session Manager hacia los puertos loopback de web y API.

El release remoto usa imagenes API, web y worker identificadas por digest inmutable.
PostgreSQL 17, Valkey y MinIO permanecen en la red Docker interna; migraciones y seed
sintetico preceden a las aplicaciones. El laboratorio no es staging ni produccion y
rechaza datos reales por contrato y configuracion.

## Evidencia operativa

- OpenTofu posterior al despliegue termino `No changes` con exit `0`; el JSON del plan
  paso `tools.aws_t1.validate`.
- `cloud-init` termino `done`; systemd y los seis contenedores quedaron saludables.
- Readiness informo PostgreSQL 17.11, esquema `V0038`, Valkey `pong` y cuatro buckets.
- EC2 observado: `t3.small`, key pair ausente, IMDSv2 `required`, hop limit `1`, root
  EBS cifrado y security group con cero reglas de ingress.
- Los puertos web/API solo se publican en `127.0.0.1`; `/entrar` devolvio HTTP 200 por
  un tunel SSM y renderizo campos etiquetados y el aviso de datos sinteticos.
- La guarda nativa de shutdown quedo programada antes de red, S3 y Docker. El timer
  persistente quedo activo antes del pull de imagenes; ambos detienen el host a las 4h.
- El archivo de configuracion sensible del host fue observado `0600:root`, sin leer o
  registrar sus valores.

## Recorrido sintetico demostrado

El smoke remoto comprobo API `ready`, rechazo no autenticado, autenticacion de Ana y
Beto, portafolios exactos de dos y una empresas, fuente activa y denegacion `403` al
intentar entrar a una empresa no autorizada. Un CSV generado para la prueba entro en
cuarentena y el worker registro su promocion con puntero a `raw`.

Se genero un `pg_dump`, se restauro en una base temporal independiente y se compararon
los conteos de historial de esquema, empresas, sujetos y decisiones de promocion. Los
conteos original/restaurado coincidieron (`38|4|5|1`); despues se retiraron la base y el
dump temporales. No se uso informacion financiera real.

## Verificacion reproducible

- `python3 -m unittest tools.aws_t0.test_validate tools.aws_t1.test_validate`:
  **50 pruebas, OK**.
- `python3 -m tools.aws_t1.validate --plan <plan-json>`: `ok: true`.
- `tofu validate` y `tofu plan -detailed-exitcode`: validos; plan final sin cambios.
- `python3 -m tools.quality_gate.cli` sobre el indice documental: `ok: true`, cero
  hallazgos; las ejecuciones de los commits funcionales tambien fueron verdes.
- SSM smoke final: success, readiness, portafolios, tenancy y carga sintetica verdes.
- SSM backup/restore: `PROMOTION_OK`, `BACKUP_RESTORE_OK` y modo de secreto `OK`.

## Hallazgos corregidos durante la ejecucion

1. PostgreSQL no podia leer el bootstrap `0600` creado por root. Se hizo world-readable
   `0444` porque contiene unicamente credenciales sinteticas versionadas; los secretos
   generados en el host permanecen `0600`.
2. El autostop se armaba demasiado tarde. La guarda nativa se programa al inicio de
   `cloud-init`, y el timer de systemd se habilita antes de descargar imagenes.
3. El plan estable del provider representa un key pair ausente como `""`, mientras un
   create usa `null`. El validador acepta ambas ausencias y sigue rechazando cualquier
   nombre real; AWS fue consultado y devolvio key pair nulo.

## Revision y limites pendientes

Security debe revisar IAM, secretos del host y frontera SSM; Architecture, la topologia
de host unico; Platform, lifecycle, costo y recuperacion; QA, el recorrido y los
validadores. El implementador y `FOUNDER-01` no cuentan como revisores independientes.

ADR-030 permanece Proposed. A-02, S-01, S1-READY, DRG-00, DRG-01 y GA-01 no se mueven.
Para usar corpus real siguen siendo obligatorios, entre otros, IdP definitivo, gestor de
secretos, RDS/persistencia decidida, TLS/dominio, observabilidad, retencion y revisiones
Security/Privacy/Legal/Accounting independientes.

## Operacion y rollback

Cerrar el tunel SSM no detiene el host. El laboratorio se detiene automaticamente tras
cuatro horas; un nuevo arranque vuelve a armar las dos guardas. Para retirar T1, generar
un `tofu plan -destroy`, validar que solo incluye la instancia, objetos del bundle y la
politica inline T1, y aplicar unicamente ese plan revisado. No usar borrado recursivo,
prune global ni destruir T0.

## Rutas liberadas

`infra/aws/t1`, contrato/documentacion/validador AWS T1, ADR-030, ficha, handoff y
registros centrales de FNC-PLT-011.
