---
id: FNC-ONB-002
status: REVIEW_PENDING
base_sha: f604c84
implementation_shas: [f3bbd4b, f4e553c, 93dac84]
tested_sha: b099c64efba1307ae2d93cf438be441f60003928
data_ceiling: synthetic_only
reviewers_pending: [Security, Backend/Architecture, Product/UX, Accessibility/QA]
---

# Handoff FNC-ONB-002 — alta sintética desde esquema vacío

## Resultado integrado

El modo local sintético permite crear sujeto, binding local, firma y membresía
owner en una transacción; después continúa al alta explícita de empresa, cuenta
y fuente de FNC-ONB-001. No depende de semillas y no confía en empresa o roles
aportados por el navegador.

La credencial local está restringida a `@demo.local`, se deriva con
PBKDF2-SHA256 y nunca aparece en respuestas, auditoría o logs. El rol runtime no
escribe directamente identidad; la función privilegiada acotada conserva RLS y
los permisos mínimos. Cualquier entorno con datos reales rechaza este proveedor
antes de tocar la base.

## Evidencia reproducible

- 5 contratos focales de registro API dentro de la imagen reproducible: OK.
- 2 pruebas focales de acciones web y aceptación de límites UAT: OK.
- CI integral `33473978646` sobre `b099c64`: PostgreSQL, esquema vacío,
  Chromium y Axe, OK.
- `tools.quality_gate.cli`, `tools.work_graph.validate` y readiness DRG-01:
  modelos válidos, con datos reales todavía no autorizados.

## Sustitución en el producto final

Esta rebanada se conserva únicamente como laboratorio sintético. FNC-IAM-004
es la ruta pública definitiva: Google/Cognito sin contraseña propia, alta
transaccional y aceptación legal versionada. No se habilita el formulario local
en UAT público ni en un futuro entorno con datos reales.

## Revisión pendiente

Security revisa la función privilegiada y el límite del proveedor local;
Backend/Architecture la atomicidad y autorización server-side; Product/UX la
continuidad a la primera empresa; Accessibility/QA el recorrido completo.
Ninguna de estas revisiones se atribuye a `FOUNDER-01` como segunda mirada.

## Rollback

Retirar consumidores web y API antes de una migración compensatoria. Las
migraciones aplicadas son forward-only y no se editan. Deshabilitar el proveedor
local no borra sujetos, firmas ni empresas existentes; una limpieza UAT separada
sigue el runbook de FNC-UAT-001.
