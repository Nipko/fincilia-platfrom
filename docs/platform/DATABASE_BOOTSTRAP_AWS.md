# Bootstrap PostgreSQL del private-pilot AWS

Este procedimiento llena el hueco entre RDS y las migraciones. No acepta
DRG-00/DRG-01, no enciende los servicios y no autoriza datos reales.

## Orden cerrado

1. La foundation debe incluir RDS privado con backup de 14 dias y el plano
   `warm` debe existir con `desired_count = 0`.
2. `prepare-secrets` consulta el endpoint RDS privado, genera o reutiliza tres
   credenciales independientes y material criptografico de aplicacion, y escribe
   cuatro versiones en Secrets Manager. Los campos de gate nacen como
   `disabled` y se conservan en ejecuciones posteriores.
3. El task `bootstrap` usa la credencial maestra administrada por RDS solo en
   esa ejecucion. El secreto administrado aporta exclusivamente usuario y
   contrasena; host y puerto proceden de atributos no secretos del recurso RDS.
   La credencial maestra de 28 bytes generada por RDS se acepta sólo para este
   canal; las credenciales de runtime conservan el mínimo independiente de 32.
   Convierte las tres contrasenas en verificadores SCRAM desde libpq antes de
   enviar DDL; crea/rota los cinco roles y termina.
4. Solo si el bootstrap termina con exit code 0 se ejecuta el task `migrator`.
5. API y worker continuan en cero. Su arranque es otro acto, posterior a las
   atestaciones KMS y revisiones humanas.

## Comandos del operador

Desde WSL, con la sesion AWS nominal vigente:

```bash
python3 -m tools.database_bootstrap.cli \
  --profile fincilia-sandbox \
  --region sa-east-1 \
  --tofu-dir infra/aws/private-pilot \
  --confirmation PREPARE_RUNTIME_SECRETS \
  prepare-secrets

python3 -m tools.database_bootstrap.cli \
  --profile fincilia-sandbox \
  --region sa-east-1 \
  --tofu-dir infra/aws/private-pilot \
  --confirmation BOOTSTRAP_AND_MIGRATE \
  bootstrap-migrate
```

La salida es deliberadamente redactada: no contiene endpoint, ARN, task ID,
usuario, DSN, contrasena ni material de firma. Los payloads AWS viajan por stdin;
no aparecen en argv ni en archivos temporales.

## Privilegios resultantes

| Rol | Login | Autoridad |
|---|---:|---|
| `fincilia_app` | si | DML concedido por migraciones; sin DDL global |
| `fincilia_worker` | si | procesamiento concedido por migraciones; sin identidad |
| `fincilia_migrator` | si | `CREATE` sobre la base y membresia NOINHERIT de autoridades |
| `fincilia_dispatch` | no | propietario acotado de funciones de cola |
| `fincilia_identity` | no | propietario acotado de alta de identidad |

Ninguno recibe `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `REPLICATION`,
`BYPASSRLS` ni herencia implicita. La aplicacion, el worker y el migrador nunca
pueden leer el secreto maestro RDS; solo el execution role del job de bootstrap
puede inyectarlo.

## Fallo y reanudacion

Los roles se serializan con advisory lock transaccional. Si el bootstrap falla,
el migrador no se inicia. `prepare-secrets` reutiliza credenciales y claves
validas ya almacenadas; repetirlo no rota accidentalmente sesiones. Para rotar
de forma intencional se necesita un procedimiento posterior con despliegue
coordinado, fuera de esta tarea.
