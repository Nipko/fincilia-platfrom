# Spike PostgreSQL de claim, outbox y fencing

FNC-DB-004 ejecuta las tres invariantes que el motor puro de idempotencia no puede
demostrar. Es un laboratorio descartable sobre PostgreSQL 17, no una migracion ni
una seleccion de arquitectura productiva.

## Modelo probado

- `claim_work` toma una fila con `FOR UPDATE SKIP LOCKED`, incrementa un fencing
  token y registra el intento. Dos sesiones sobre el mismo trabajo no comparten
  lease ni producen dos claims.
- `commit_effect` valida dueño, token y vencimiento bajo bloqueo. El efecto y el
  evento outbox viven en la misma transaccion; una excepcion intermedia revierte
  ambos.
- Un commit exitoso deja el outbox `pending`. Otro dispatcher puede recuperarlo;
  `delivery_receipt(event_id)` hace idempotente el efecto visible del laboratorio.
- Reclamado un lease vencido, el token anterior devuelve `stale_lease` antes de
  insertar efecto u outbox. No se confia solo en el nombre del worker.

El rol runtime no tiene DDL ni escritura directa sobre tablas y solo ejecuta las
cuatro funciones declaradas en el contrato. Compose no publica puertos y la red es
interna. El runner fija proyecto, fichero, servicio, entorno y rutas; la unica
limpieza con volumen se limita a `fincilia-concurrency-spike`.

## Ejecucion

```powershell
python -m tools.concurrency_spike.validate
python -m unittest tools.concurrency_spike.test_validate -v
python -m tools.concurrency_spike.cli run --repeat 2
```

Un verde prueba las invariantes del motor real. No aprueba broker, scheduler,
workflow, migracion productiva, ADR o gate. Todo dato del laboratorio es sintetico.
