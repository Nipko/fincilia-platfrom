# ADR-038 — planes, entitlements y facturación

- Estado: **Proposed; cobros reales desactivados**
- Fecha: 2026-08-31
- Tarea: FNC-BIL-001
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

## Configuración pendiente para el final

Proveedor de pagos, razón social facturadora, país/impuestos, precios, monedas,
días de trial, límites exactos y política de morosidad/cancelación.

