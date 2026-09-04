---
id: FNC-PLT-016
status: REVIEW_PENDING
base_sha: ae8aeb7fd77b0440d025749dbd3446b5474b2f0a
code_sha: d22a13fbd837c231aa17416115c5855080b629e9
data_ceiling: synthetic_only_until_DRG-00
author: Codex principal dev + Integration Steward
independent_reviewers: [Database, Security, Platform/SRE, QA]
---

# Handoff FNC-PLT-016 — bootstrap seguro de PostgreSQL en AWS

## Resultado

Se cerró el hueco técnico entre RDS administrado y `V0001`–`V0029` sin
convertir el usuario maestro en identidad de runtime. El flujo queda cerrado y
reanudable:

1. el controlador comprueba RDS privado, cifrado, `available` y con nombre
   exacto;
2. genera o reutiliza tres credenciales independientes y las claves de
   aplicación en Secrets Manager, conservando atestaciones existentes;
3. un task Fargate efímero y separado crea o rota los roles mediante
   verificadores SCRAM generados por libpq;
4. sólo después de exit code cero se ejecuta el migrador;
5. API y worker deben permanecer en `desired_count = 0` y los datos reales
   continúan deshabilitados.

El secreto maestro RDS y el secreto de roles sólo pueden ser inyectados por el
execution role del task de bootstrap. Este task no tiene servicio ECS, IP
pública, ejecución remota ni privilegios de aplicación. Los payloads con
secretos viajan por stdin hacia AWS CLI; los reportes no exponen ARN, endpoint,
DSN, usuario, task ID ni material criptográfico.

## Contrato de privilegios

- `fincilia_app`, `fincilia_worker` y `fincilia_migrator`: login,
  `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, `NOREPLICATION`,
  `NOBYPASSRLS`, límite de 20 conexiones.
- `fincilia_dispatch` y `fincilia_identity`: sin login ni contraseña y con los
  mismos límites globales.
- sólo el migrador recibe membresía `NOINHERIT` a las dos autoridades y
  `CREATE` sobre la base exacta.
- `PUBLIC`, app y worker pierden `CREATE`/`TEMPORARY` sobre la base y `PUBLIC`
  pierde `CREATE` sobre el esquema `public`.

## Evidencia reproducible

| Verificación | Resultado |
| --- | --- |
| suites Platform, bootstrap, identidad, supply chain y work graph | 159 pruebas, OK |
| `tools.database_bootstrap.test_control` | 7 pruebas, OK |
| imagen API contra PostgreSQL 17.11 real | 5 pruebas, OK |
| repetición del bootstrap real | roles idempotentes, credenciales rotadas y privilegios mínimos, OK |
| `tofu fmt -check -recursive` y `tofu validate` | OK, OpenTofu 1.12.6 |
| `tools.aws_private_pilot.validate` | contrato y fuentes válidos; despliegue/datos reales en `false` |
| `tools.work_graph.validate` | 142 tareas, grafo válido |
| `tools.test_catalog.cli validate` | modelo válido; cero blockers |
| `tools.quality_gate.cli` sobre índice Git | OK, cero hallazgos |
| plan cold más reciente | 7 create, 135 no-op, 2 read, 5 update, 0 delete; válido |
| plan warm más reciente | 33 create, 135 no-op, 2 read, 5 update, 0 delete; válido; no aplicado |

La prueba de PostgreSQL usó una red Docker interna y un contenedor sin volumen.
El contenedor y la red se eliminaron al finalizar; no existe dato que recuperar.

## Límites y bloqueos preservados

- La cuenta AWS aún impide crear el RDS con 14 días de retención bajo el plan
  gratuito nuevo. No se redujo el control: se requiere upgrade directo al plan
  Paid; los créditos permanecen aplicables según las condiciones de la cuenta.
- El plano warm, los secretos iniciales, el bootstrap remoto, las migraciones y
  los servicios no se aplicaron.
- El validador de supply chain conserva un blocker histórico
  `SUP-PROVENANCE-PENDING` y seis coberturas de actualización no monitorizadas;
  este cambio no los oculta ni los reclasifica.
- DRG-00 y DRG-01 siguen `not_met`; no se acepta información personal o
  financiera real ni operación piloto real.
- Database, Security, Platform/SRE y QA deben revisar independientemente. El
  Founder puede ser accountable owner, pero no su propio revisor independiente.

## Reanudación

Después del upgrade directo de la cuenta: aplicar nuevamente foundation cold,
publicar imágenes inmutables por digest, aplicar warm con servicios en cero,
ejecutar `prepare-secrets`, ejecutar `bootstrap-migrate`, verificar restauración
y atestaciones, y sólo entonces considerar el encendido. Los comandos exactos
están en `docs/platform/DATABASE_BOOTSTRAP_AWS.md`.

## Rollback

Antes de ejecutar remotamente, revertir el código sólo elimina task definitions,
roles IAM y el contenedor lógico de secretos que aún no se han creado. Después
de una ejecución remota, los roles PostgreSQL y versiones de Secrets Manager se
tratan como estado persistente: no se borran automáticamente; se rota a una
versión anterior y se aplica una migración de reversión revisada.
