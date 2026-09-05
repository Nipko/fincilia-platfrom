---
task: FNC-NTF-002
status: REVIEW_PENDING
base_sha: cfc6528
implementation_sha: 3780ff0fb125e409c7a3fab165e87231b7e459b3
data_ceiling: synthetic_only
gate_effect: none
independent_review: pending
---

# Handoff FNC-NTF-002 — despacho durable de correo

## Resultado

La intención company-scoped puede llegar a una entrega durable mediante un
worker con credencial PostgreSQL propia. La dirección verificada se persiste
solo como referencia HMAC y ciphertext KMS ligado a esa referencia. Las
plantillas cerradas no admiten importes, cuentas, documentos ni adjuntos.

El protocolo usa lease y fencing para el trabajo previo. Justo antes de SES
arma el intento como `uncertain` en un commit independiente. Como SES no ofrece
idempotency key para `SendEmail`, una caída posterior nunca vuelve a encolar el
correo: se conserva incierto para conciliación humana. Solo un rechazo
inequívoco puede reintentar, con máximo y backoff en PostgreSQL.

## Migraciones y privilegios

- V0059 agrega destino cifrado, intentos, feedback minimizado y las funciones
  de claim/finalización.
- V0060 agrega la frontera at-most-once y settlement por fencing token.
- V0061 hace única la referencia digest-only del mensaje, evitando asociar un
  rebote a más de una entrega.
- `fincilia_notification_worker` solo ejecuta cinco funciones; no tiene acceso
  directo a identidad, finanzas, destinos, intentos ni entregas.
- Las funciones privilegiadas pertenecen a
  `fincilia_notification_dispatch`, un rol `NOLOGIN` sin DDL.

## Evidencia reproducible

| Superficie | Resultado |
|---|---|
| API completa | 205 pruebas, OK |
| Worker | 7 pruebas, OK; healthcheck `healthy` con proveedor deshabilitado |
| PostgreSQL 17 | 6 pruebas, OK; ACL, concurrencia, fencing, retry, uncertain y feedback |
| Migraciones | V0061 aplicada y replay `mutated: false`, head V0061 |
| Web | lint, typecheck y 298 pruebas, OK |
| Navegador | 1 Chromium y 1 Axe, OK |
| Contratos | migration readiness, runtime config y local stack, OK |
| Plataforma | 50 pruebas de bootstrap/stack, OK |
| Índice Git | quality gate, sin hallazgos |

## Defectos encontrados al ejecutar

1. Un fallo al persistir después de que SES aceptara podía dejar expirar el
   lease y duplicar el correo. V0060 lo convierte en at-most-once fail-closed.
2. Referencias de proveedor repetidas volvían ambiguo el feedback. V0061 las
   hace únicas.
3. Una propiedad no allowlisted en el log de arranque detenía el worker. El
   evento usa ahora únicamente campos permitidos y el contenedor queda sano.

## Límites y siguiente revisión

El adaptador está listo, pero `notification_provider=disabled` es el valor por
defecto. No se verificó una identidad SES, no se envió correo, no existe todavía
el ingreso cloud de feedback ni se movieron DRG-00, DRG-01 o GA-01. Privacy,
Security, Platform y QA deben revisar destino cifrado, funciones privilegiadas,
operación at-most-once y runbooks antes de activarlo.

Rollback de aplicación: volver al release anterior, compatible con el esquema
expandido. Las migraciones son forward-only y no se eliminan ni reescriben.
