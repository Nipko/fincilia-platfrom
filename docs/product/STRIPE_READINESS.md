# Stripe readiness para UAT

FNC-BIL-002 deja la integración completa pero apagada. No hay claves, productos,
precios, clientes ni cobros creados por el repositorio. La configuración final
se hace en Stripe test mode y AWS Secrets Manager después de DRG-00, DRG-01 y la
revisión DB-G03.

## Superficie ya implementada

- `POST /api/v1/firms/{firm_id}/billing/checkout`: manager activo, plan y precio
  resueltos en servidor, Checkout alojado e idempotente.
- `POST /api/v1/firms/{firm_id}/billing/portal`: manager activo y customer ya
  ligado; la referencia exacta nunca aparece en la respuesta.
- `POST /api/v1/billing/webhooks/stripe`: sin sesión de usuario, cuerpo crudo
  máximo 256 KiB y autoridad exclusiva de `Stripe-Signature`.
- `GET /api/v1/billing/plans` y `GET /api/v1/firms/{firm_id}/billing`: catálogo,
  estado normalizado, uso e historial sin referencias exactas del proveedor.

Endpoint público de webhook:

`https://fincilia.com/api/v1/billing/webhooks/stripe`

Eventos allowlisted:

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

Un evento firmado no basta para crear la primera relación: debe corresponder a
una reserva Checkout vigente creada por un manager. Duplicados byte-identicos
devuelven éxito idempotente y una colisión de ID/digest se rechaza. La
materialización se serializa por firma; una baja atrasada de una suscripción
anterior no puede cancelar la actual. Fallos temporales del proveedor o de
PostgreSQL devuelven 503 para que Stripe reintente.

## Datos que se suministran al final

En el secreto de aplicación existente, nunca en Git, tfvars, tickets o prompts:

- `FINCILIA_STRIPE_SECRET_KEY`: clave `sk_test_...` restringida a UAT.
- `FINCILIA_STRIPE_WEBHOOK_SECRET`: `whsec_...` de este endpoint exacto.

Configuración no secreta:

- `FINCILIA_PAYMENT_PROVIDER=stripe`
- `FINCILIA_STRIPE_API_VERSION=2026-08-26.dahlia`
- `FINCILIA_STRIPE_PUBLIC_ORIGIN=https://fincilia.com`
- `FINCILIA_STRIPE_AUTOMATIC_TAX_ENABLED=false`
- `FINCILIA_PAYMENTS_ENABLED=true`

AWS solo inyecta los dos secretos si `payments_enabled=true`. Al activar, la API
también exige OIDC administrado, datos reales solicitados, Secrets Manager y una
atestación DRG-01 vigente firmada con KMS; de lo contrario no arranca.

## Decisiones comerciales diferidas

Para cada uno de Inicio, Negocio y Contador se debe aprobar una versión con
moneda, monto minor, periodo de prueba, límites e `price_id` Stripe exacto. Un
plan sin mapeo activo aparece como “Precio por publicar” y no permite Checkout.

También quedan para Finance/Legal: país facturador, dirección y tax IDs en
Stripe, nexo fiscal, Automatic Tax, métodos de pago, facturación, prorrateo,
dunning, reembolsos y momento de cancelación. Ninguno tiene un default comercial
inventado por código.

## Evidencia antes de habilitar

1. Revisión independiente de V0064/V0065/V0066 y las seis funciones definer.
2. PostgreSQL real: RLS, concurrencia, duplicados, cancelación e inbox mínimo.
3. Stripe test mode: alta, cambio, pago fallido, recuperación, portal y baja.
4. Confirmar que logs, auditoría y respuestas no contienen claves, payloads,
   customer IDs ni datos de tarjeta.
5. Revisión Finance/Legal y plan de rollback (`payments_enabled=false`).

Las claves live y los cobros reales pertenecen a GA-01 y no son aceptados por
esta configuración UAT.
