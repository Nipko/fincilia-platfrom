---
id: FNC-WEB-005
title: Cierre funcional de experiencias web parciales
status: in_progress
implementer: Codex principal dev + Integration Steward
base_sha: e4a5764
gate: none
gate_effect: none
data_ceiling: synthetic_only
independent_reviewers: [Product, Accounting, Privacy, Accessibility/QA]
---

# Resultado esperado

Cerrar la experiencia web de las cuatro capacidades que el inventario funcional
mantiene parciales: formatos y OCR, avisos, calidad/riesgo y planes/uso. La web
debe mostrar capacidad, estado, límites, historial y siguiente acción sin
presentar un adaptador apagado como servicio activo.

# Rutas permitidas

- `apps/web/src/app/cuenta/**`
- `apps/web/src/app/recordatorios/**`
- `apps/web/src/app/calidad/**`
- `apps/web/src/app/empresas/[companyId]/documentos/**`
- `apps/web/src/components/capability-status.*`
- `apps/web/src/components/__tests__/capability-status.test.tsx`
- `apps/web/src/lib/web-capabilities.*`
- `apps/web/src/lib/__tests__/web-capabilities.test.ts`
- `apps/web/tests/e2e/web-capability-closure*`
- esta ficha y su handoff
- registros centrales por Integration Steward

# Rutas prohibidas

- API, worker, migraciones, infraestructura y configuración de proveedores.
- Autorización, RLS, semántica financiera, datos reales o IA externa.
- Precios inventados, checkout ficticio, correo simulado o fraude confirmado.
- Aceptación de DRG-00, DRG-01, GA-01 o revisiones humanas.

# Criterios de aceptación

1. Planes muestran límites, consumo, estado comercial e historial sin inventar
   precios ni convertir una evaluación en suscripción pagada.
2. Avisos muestran resumen, preferencias, estados y causas de supresión con
   nombres comprensibles y fechas navegables.
3. La ingesta publica una matriz exacta de CSV, XLSX, ODS y PDF, distinguiendo
   texto embebido de OCR requerido.
4. Calidad conserva el lenguaje de señal, explica cobertura y separa reglas
   deterministas de capacidades futuras.
5. Estados vacío, parcial, restringido y proveedor apagado son accesibles y no
   dependen únicamente de color.
6. No se añade una dependencia ni se cambia un contrato server-side.
7. Unitarias, lint, tipos, build, Chromium y Axe focales quedan verdes.
