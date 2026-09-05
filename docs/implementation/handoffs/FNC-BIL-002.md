---
task: FNC-BIL-002
status: REVIEW_PENDING
base_sha: 88781f7
implementation_sha: a90b73c5018ca4377bf717bc12c162c033f5041c
integration_sha: pending_remote_push_and_ci
data_ceiling: synthetic_only
gate_effect: none
independent_review: pending
---

# Handoff FNC-BIL-002 — Stripe provider-ready

## Resultado

La plataforma tiene una frontera completa de cobro recurrente con Stripe,
apagada por defecto y preparada para recibir configuración al final:

- Checkout y Customer Portal alojados por Stripe;
- plan, versión y `price_id` resueltos exclusivamente en servidor;
- webhook sobre cuerpo crudo con límite de 256 KiB y firma con tolerancia de
  300 segundos;
- relectura del snapshot vigente para que la entrega fuera de orden no gobierne
  el estado;
- inbox digest-only, anti-replay, serialización por firma y transiciones de
  suscripción append-oriented;
- referencias exactas `customer`, `subscription`, `price` y `session` aisladas
  en tablas provider-only;
- UI de plan, uso, Checkout, Portal e historial sin PAN/CVV ni referencias del
  proveedor;
- task definition AWS que no inyecta secretos mientras los pagos estén
  apagados y arranque fail-closed si faltan OIDC, Secrets Manager o atestación
  DRG válida.

El retorno exitoso del navegador nunca activa un plan. Solo el webhook Stripe
verificado puede materializar capacidad comercial.

## Cambios por capa

1. **API:** adaptador Stripe con SDK/API fijados, rutas autenticadas para
   Checkout/Portal, webhook público firmado y errores estables 400/409/503.
2. **PostgreSQL:** V0064 crea catálogo provider-only, bindings, reservas e
   inbox; V0065 expone solo readiness booleana; V0066 serializa por firma,
   rechaza colisiones y descarta bajas de una suscripción anterior.
3. **Web:** `/cuenta` muestra planes, límites, uso, estado e historial; solo
   habilita Checkout si el precio exacto está publicado, y solo abre hosts
   Stripe allowlisted.
4. **AWS:** `payments_enabled=false` y Automatic Tax `false` por defecto; los
   dos secretos se referencian condicionalmente desde Secrets Manager.
5. **Gobierno:** Stripe fue elegido por Founder, pero precios, impuestos,
   cobros y gates continúan sin aprobarse. ADR-038 permanece `Proposed`.

## Evidencia obtenida

| Verificación | Resultado |
|---|---|
| Contrato puro del adaptador Stripe | 9 pruebas, OK |
| Web completa | 55 archivos, 299 pruebas, OK |
| Web lint y TypeScript | OK |
| Validador AWS private pilot | 46 pruebas y contrato, OK; pagos/datos `false` |
| Runtime config | 67 variables, OK |
| Migration readiness | V0001–V0066, OK |
| Web functional status | 100 % implementación, 62 % aceptación sintética, 30 % operabilidad |
| Work graph | OK; rutas FNC-BIL-002 liberadas |
| Golden/mutation harness | 14 golden y 68 mutaciones/9 validadores, OK |
| Quality gate del índice en commits incrementales | Sin hallazgos |

Las suites HTTP y PostgreSQL están escritas, incluida RLS, ACL, concurrencia de
evento igual y distinto, colisión de payload, baja atrasada, portal y ledger
append-only. No se declaran ejecutadas: WSL devuelve
`Wsl/EnumerateDistros/Service/E_ACCESSDENIED`, el Python disponible no incluye
FastAPI/Psycopg y la unidad C: quedó sin espacio suficiente para reconstruir
contenedores o instalar el lock. CI debe correrlas sobre el commit integrado.

## Commits incrementales

- `464d072` reserva y contrato de tarea.
- `d26c19a` autoridad de pago API/PostgreSQL.
- `7eb07e9` experiencia alojada en la web.
- `5f4308a` precio no configurado oculto y fail-closed.
- `9897473` activación AWS gobernada.
- `058379b` serialización, anti-replay y reintentos.
- `a90b73c` readiness y avance funcional.

## Configuración deliberadamente diferida

No hay claves, productos, prices, clientes o cobros reales en el repositorio.
Al cerrar los planes se crean tres Prices test-mode y se registran sus IDs con
la versión comercial aprobada. Después se suministran, únicamente mediante
Secrets Manager:

- `FINCILIA_STRIPE_SECRET_KEY=sk_test_...`
- `FINCILIA_STRIPE_WEBHOOK_SECRET=whsec_...`

El endpoint a registrar es
`https://fincilia.com/api/v1/billing/webhooks/stripe`. La lista exacta de
eventos y variables está en `docs/product/STRIPE_READINESS.md`.

## Revisión y aceptación pendientes

- Database/Security: seis funciones `SECURITY DEFINER`, V0064–V0066, ACL, RLS,
  advisory lock y anti-replay.
- Finance/Legal/Product: moneda, precios, trial, impuestos, prorrateo, dunning,
  reembolsos y cancelación.
- Privacy: rol de Stripe, DPA/subencargado, retención y minimización.
- QA/Architecture: ejecución PostgreSQL, HTTP, Stripe test mode y rollback.
- CI verde sobre el commit integrado y actualización de `integration_sha`.

Hasta completar esas evidencias el estado correcto es `REVIEW_PENDING`; no se
mueven DRG-00, DRG-01, DB-G03 ni GA-01.

## Rollback

El rollback operativo es `payments_enabled=false`, que retira Checkout, Portal,
webhook y secretos del runtime. Las migraciones son expand-only/forward-only:
V0064–V0066 no se reescriben ni se eliminan y el historial queda disponible
para auditoría. Una corrección posterior usa V0067 o superior.
