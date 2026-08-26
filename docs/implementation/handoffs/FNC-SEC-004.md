---
task: FNC-SEC-004
status: REVIEW_PENDING
base_sha: 9ae4e1d
implementation_sha: 028fd1b
data_ceiling: synthetic_only
reviewers_pending: [Security, Database/Architecture]
---

# Handoff FNC-SEC-004

## Resultado

`UD-ISSUED-CONTEXT` ya tiene forma productiva local. V0021 crea una capability
company-scoped para trabajo que sobrevive una petición y un tombstone separado
para revocarla sin reescribir la emisión. El kernel emite de forma idempotente,
revalida contra la autoridad actual y audita emisión, uso y revocación.

Las sesiones HTTP cortas no crean estas filas: continúan revalidándose online.
Tampoco se añadió un endpoint o una pantalla sin consumidor real.

## Controles demostrados

- `FORCE RLS` en emisión y revocación, con prueba cross-company.
- Runtime tiene solo `SELECT/INSERT`; `UPDATE/DELETE` fallan por privilegio.
- FK compuesto evita combinar company, firm y engagement de rutas distintas.
- El lock compartido sobre `authorization_version` ordena emisión y revocación
  concurrente; una fotografía obsoleta no puede emitir.
- Cada uso exige sujeto, membership, engagement y grant vivos, misma versión,
  propósito/recurso exactos, no expiración y ausencia de tombstone.
- Referencia de recurso, idempotencia y firma de solicitud son HMAC con dominio
  y company; no se almacena el valor de entrada.
- Reusar una clave idempotente con otra semántica falla cerrado.

## Evidencia

```text
python -m tools.migration_readiness.validate
wsl ... sh infra/local/up.sh
wsl ... docker compose ... run --rm migrate python -m unittest -v db.tests.test_issued_authorization_context
wsl ... docker compose ... run --rm migrate
```

Resultados: V0021 aplicada sobre V0020; replay `mutated=false`, head V0021;
8/8 pruebas PostgreSQL 17, 14/14 casos golden y 68/68 mutaciones verdes. La
primera ejecución del caso de FK reveló
que FORCE RLS también ocultaba Andinos al migrador bajo contexto Espiga; el
fixture se corrigió para resolver cada empresa en su alcance antes de intentar
la combinación inválida.

La suite API ejecutada desde el Python global de Windows no era importable porque
ese intérprete no instala los paquetes del monorepo; en la imagen oficial de CI
`migrate` corrieron 107/107 pruebas verdes. S1 conserva un único blocker: la
revisión humana independiente por personas distintas.

## Límites y siguientes consumidores

Solo datos sintéticos. No habilita enlaces públicos, schedules, exports
programados, producción, DRG-00 ni DRG-01. El primer consumidor durable debe:

1. resolver company y principal server-side;
2. emitir con un `TenantContext` vivo y una clave HMAC dedicada desde Vault/KMS
   fuera de local;
3. revalidar antes de leer y de publicar/entregar;
4. propagar solo `context_id`, nunca el recurso en claro por colas o logs.

Security y Database/Architecture deben revisar V0021 y el kernel; el implementador
y `FOUNDER-01` no cuentan como segunda mirada independiente.

## Rollback

Retirar primero consumidores. La migración es forward-only: no se edita V0021.
Una compensación futura revoca INSERT, conserva emisiones/auditoría según L-01 y
solo elimina tablas después de una migración explícita de cualquier contexto vivo.
