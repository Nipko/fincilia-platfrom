# Eventos, outbox, retries y dead letters

Estado: `Review pending` · Tarea: `FNC-ARC-004` · Datos: solo sintéticos.

Este contrato define cómo Fincilia comunica hechos comprometidos y recupera fallos sin
duplicar efectos. No selecciona proveedor de cola/Temporal, no crea migraciones y no
habilita conectores o efectos financieros productivos.

## 1. Flujo seguro

```text
transacción de dominio
  └─ cambio + outbox atómico
       └─ dispatcher con claim/fencing
            └─ entrega al menos una vez
                 └─ inbox + efecto consumidor atómico
                      └─ delivery attempt / reconciliación
```

Un evento comunica un hecho ya comprometido. No se usa para completar una invariante que
debe resolverse dentro de la transacción originaria.

## 2. Fuentes de verdad separadas

| Componente | Autoridad |
|---|---|
| PostgreSQL | Estado de dominio visible, definición del job, outbox, inbox y estado visible |
| Workflow durable | Historia, timers, compensaciones y esperas humanas |
| Cola | Entrega y backoff de trabajo sin estado |
| Valkey | Progreso/heartbeat/cache efímeros |
| Analytics | Proyección reconstruible |

Perder Valkey degrada la barra de progreso; nunca pierde un retry ni cambia un cierre.
La historia del workflow explica ejecución, pero no reemplaza el estado financiero.

## 3. Envelope y compatibilidad

Todo evento fija ID, nombre, schema/version, productor, aggregate/version, company scope,
purpose, clasificación, correlación/causación, idempotency hash y digest del payload. El
scope procede del servidor. Datos grandes se referencian mediante objeto inmutable + hash.
Secretos y datos prohibited no entran al mensaje; payload/raw tampoco entra a telemetría.

No existe orden global. `aggregate_version` detecta duplicados, stale events y gaps. Un
gap pausa ese agregado y reconcilia; no se resuelve con last-write-wins.

Cambio compatible añade un campo opcional sin cambiar significado. Un cambio breaking
crea major schema y migración explícita. Schema desconocido termina en dead letter sin
efecto; nunca se interpreta con `latest`.

## 4. Outbox e inbox

El módulo productor invoca el port de Platform dentro de su transacción; no escribe el
repositorio ajeno directamente. El dispatcher reclama con `SKIP LOCKED` o CAS y fencing.
Solo marca published después del ack del broker. No elimina la evidencia al publicar.

El consumidor reclama `(consumer_id,event_id)` por constraint y compara digest. Mismo ID
y digest devuelve el resultado previo; digest distinto es conflicto/señal de seguridad.
Receipt y efecto local confirman juntos. Un crash no puede dejar receipt exitoso sin efecto.

## 5. Un solo owner de retry

| Trabajo | Owner del calendario |
|---|---|
| Dispatch de outbox | Dispatcher de outbox |
| Job sin estado | Cola administrada |
| Workflow/timer/espera humana | Motor durable |
| Efecto externo idempotente | Cola o workflow padre; nunca adaptador |
| Efecto externo no idempotente | Ninguno automático; revisión humana |

El adaptador clasifica `retryable`, `rate_limited`, `fatal`, `requires_human` o `unknown`
y falla rápido. El circuit breaker admite/bloquea; no agenda. Cada policy versionada fija
intentos, tiempo transcurrido, timeout, deadline, costo, backoff y agotamiento. No se
inventan defaults globales en esta tarea.

## 6. Dead-letter y replay

Agotar presupuesto o recibir schema/fallo inseguro crea un item visible, company-scoped y
sin payload raw. Conserva referencias, digest, clasificación, policy, owner y auditoría.

Replay exige reautorizar, conservar la misma clave de efecto, comprobar schema o migración,
elegir policy explícita y crear un nuevo attempt. No muta el item ni evento original. Un
efecto financiero/externo requiere aprobación humana. Descartar exige actor y razón.

## 7. Efectos externos

Auto-retry requiere contrato de idempotencia del proveedor, ledger local y reconciliación.
Un timeout de resultado desconocido se reconcilia antes de reintentar. Sin idempotencia
verificada pasa a humano. Este contrato no habilita pagos, fondos o credenciales.

## 8. Autorización, revocación y observabilidad

Jobs fijan company y `authorization_version`; revalidan antes de leer y antes de publicar
o efectuar egress. Revocar bloquea trabajo pendiente/capabilities. Replay de DLQ vuelve a
autorizar. Logs y métricas usan allowlist; nunca payload, error raw, monto, cuenta, NIT,
referencia, token o secreto.

## 9. Implementación posterior

PLT-005 debe demostrar en PostgreSQL real: atomicidad, dos claims concurrentes, fencing,
crashes en cada frontera, replay e aislamiento por company. La elección de cola/workflow,
región y valores numéricos requiere owner humano y evidencia de costo/operación.

## 10. Verificación

```powershell
python -m tools.event_model.validate
python -m unittest tools.event_model.test_validate -v
```

El JSON es autoritativo para el contrato ejecutable. Ningún resultado supera S1-READY o
autoriza datos reales por pasar estas comprobaciones.
