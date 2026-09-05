# ADR-038 — planes, entitlements y facturación

- Estado: **Proposed; cobros reales desactivados**
- Fecha: 2026-08-31; ampliada 2026-09-04
- Tareas: FNC-BIL-001, FNC-BIL-002
- Owners: Product + Finance + Security, accountable FOUNDER-01
- Gates: DRG-00, DRG-01, GA-01

## Decisión propuesta

- El catálogo versionado contiene tres familias de plan, pero precio, moneda e
  impuestos son configuración comercial, no constantes repartidas por el código.
- Una suscripción pertenece a la firma. Los entitlements derivados controlan
  límites de capacidad; jamás conceden acceso financiero ni sustituyen RBAC/RLS.
- Privacidad, seguridad, borrado, acceso a evidencia propia y exportación básica
  no se bloquean por plan.
- Uso se registra en un ledger append-only con claves idempotentes y dimensiones
  allowlisted. No contiene documentos ni valores financieros.
- Billing posee customer, subscription, invoice reference y credit ledger; no
  posee movimientos financieros de las empresas.
- El proveedor de pagos se integra por port + webhook firmado + inbox. Ningún
  evento del cliente activa un plan sin verificación server-side.
- `payments_enabled=false` impide checkout, cobro y webhooks reales, pero permite
  probar catálogo, trial, entitlements, consumo y consola con datos sintéticos.

## Selección técnica autorizada por Founder — 2026-09-04

- Stripe es el proveedor seleccionado. Esta adjudicación permite implementar la
  frontera; no aprueba precios, impuestos, cobros reales ni gates.
- Checkout y Customer Portal son alojados por Stripe. Fincilia nunca captura ni
  almacena PAN/CVV y solo devuelve URLs HTTPS de hosts Stripe allowlisted.
- El webhook recibe el cuerpo crudo, valida `Stripe-Signature` con tolerancia
  acotada y deduplica antes de materializar. El retorno del navegador nunca
  activa una suscripción.
- Ante eventos fuera de orden se relee el snapshot vigente de la suscripción;
  `customer.subscription.deleted` usa su objeto final firmado, porque el recurso
  puede dejar de ser recuperable. Una caída de consulta responde 503 para pedir
  reintento, mientras una firma inválida responde 400.
- SDK `stripe==15.6.1` y API `2026-08-26.dahlia` quedan fijados. Su actualización
  exige lock, pruebas de contrato y revisión de changelog.
- Las referencias exactas de customer, subscription, price y Checkout viven en
  tablas provider-only. Producto ve únicamente digests, estados normalizados y
  un booleano de readiness del plan.
- En UAT solo se aceptan claves `sk_test_`. Automatic Tax permanece apagado
  hasta cerrar la postura tributaria de Parallext LLC.

## Configuración pendiente para el final

Razón social facturadora operativa en Stripe, país/impuestos, precios, monedas,
días de trial, límites exactos, métodos de pago y política de
morosidad/cancelación. La decisión sigue `Proposed` hasta revisión independiente
de Product, Finance, Security, Privacy, Architecture y Database.
