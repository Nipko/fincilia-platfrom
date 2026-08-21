# Evidencia, deduplicación e idempotencia

Estado: `Review pending` · Tarea: `FNC-DOM-004` · Datos: solo sintéticos.

Este contrato evita que una entrega repetida produzca un segundo efecto y, a la vez,
evita que dos transacciones legítimas iguales sean colapsadas. No es una migración SQL,
no habilita merges productivos y no supera S1-READY.

## 1. Cinco identidades, no una clave universal

| Capa | Pregunta | Identidad fuerte permitida |
|---|---|---|
| Entrega | ¿Ya recibimos este comando/webhook? | Sí, dentro del scope del emisor y comparando payload |
| Artefacto | ¿Son los mismos bytes de la misma fuente? | Sí, SHA-256 de bytes originales + company/source |
| Observación | ¿Es el mismo registro emitido por la fuente? | Solo con contrato de ID del proveedor verificado |
| Evento económico | ¿Varias evidencias describen el mismo movimiento real? | No por atributos de negocio; exige decisión trazable |
| Efecto publicado | ¿Ya aplicamos esta transición versionada? | Sí, clave de publicación + transacción/outbox |

Una identidad en una capa no prueba identidad en otra. El mismo archivo puede contener
dos filas legítimas iguales; dos archivos diferentes pueden solaparse; un webhook puede
repetirse sin que el evento económico deba recrearse.

## 2. Identidades duras autorizadas

Solo se permiten estos patrones:

1. Artefacto exacto: `company + data_source + SHA256(bytes originales)`.
2. Entrega de proveedor: `connection + HMAC(provider_event_id)`, con digest del payload.
3. Comando: `company + principal + operación + HMAC(idempotency_key)`, con digest del payload validado.
4. Procesamiento: artefacto + versiones de parser, receta, esquema y engine release.
5. Publicación: company + agregado + transición + versión del agregado.

La comprobación es atómica en PostgreSQL mediante constraint/compare-and-set. Un
`SELECT` previo, lock de Valkey o mutex de proceso no es garantía. Misma clave y mismo
payload devuelve la referencia original; misma clave y payload distinto genera conflicto,
no un éxito aparente.

## 3. Lo que nunca será UNIQUE

Fecha, importe, dirección, referencia, contraparte, localizador y fingerprint derivado
solo sirven para bloquear y ordenar candidatos. Tampoco es UNIQUE la combinación completa
de esos atributos. El fixture `SYN-LEGIT-IDENTICAL` exige que dos pagos distintos e
idénticos sigan siendo dos movimientos posibles.

Un fingerprint candidato es HMAC versionado de rasgos normalizados. No es identidad, no
anonimiza los datos y no se registra en logs junto con valores raw.

## 4. IDs de proveedor

Todo conector empieza `unverified`. Un ID de transacción solo puede convertirse en
identidad fuerte cuando existe evidencia de namespace, alcance, inmutabilidad o revisiones,
replay/id reuse, versión de conector, owner y revisor independiente. Reutilización,
colisión o deriva suspende el contrato y vuelve a modo candidato fail-closed.

El ID de entrega y el ID del registro financiero son conceptos distintos. Verificar firma
del webhook ocurre antes de reclamar su clave idempotente.

## 5. Dedupe económico

`dedupe_candidate` y `dedupe_decision` pertenecen a Finance. El par se ordena por UUID
para evitar candidatos duplicados, pero esa unicidad solo identifica el expediente de
revisión; no afirma que los movimientos sean el mismo evento.

Una decisión guarda company, ambos movimientos, razón, evidencia, actor, regla, engine
release y auditoría. El historial es append-only. Revertir crea una nueva decisión que
referencia la anterior. Nunca se borra evidencia ni un movimiento físicamente.

En E0 `confirmed_same_event` no ejecuta merge, void ni supersession: Accounting y
Architecture deben definir primero la semántica contable. El auto-dedupe permanece
deshabilitado.

## 6. Concurrencia, retries y outbox

- Workers reciben al menos una vez; el efecto visible se hace exactamente una vez por
  idempotencia del consumidor y clave única de publicación.
- El cambio de dominio y el outbox se confirman en la misma transacción.
- Un consumidor registra/aplica el efecto atómicamente; nunca confirma receipt antes del efecto.
- Trabajos con lease usan fencing token; un worker vencido no puede escribir.
- Solo el workflow durable de Platform programa retries. Handler, conector y broker no
  compiten con calendarios independientes.
- Un crash posterior al commit pero previo a entrega deja el outbox pendiente y recuperable.

## 7. Seguridad y privacidad

El scope de company procede del contexto autorizado server-side. No se crean candidatos
entre companies. Logs solo reciben hashes/HMAC y metadatos allowlisted, nunca payload,
referencia, cuenta o provider ID raw. Una colisión o reutilización de ID emite señal de
seguridad y bloquea publicación hasta resolverla.

## 8. Gates de implementación

Antes de migraciones productivas se requiere:

- revisión Accounting de same-event/supersession;
- revisión Architecture de constraints, transacciones y retry ownership;
- revisión Security de replay, firmas, HMAC, logs y fencing;
- contrato por conector con pruebas de namespace/reutilización;
- pruebas concurrentes reales en PostgreSQL para cada constraint;
- linaje y engine release completados por DOM-005.

## 9. Verificación

```powershell
python -m tools.idempotency_model.validate
python -m unittest tools.idempotency_model.test_validate -v
```

El JSON es la especificación ejecutable. El documento explica intención y límites; si
difieren, la discrepancia bloquea revisión y debe corregirse explícitamente.
